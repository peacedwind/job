import asyncio
from datetime import date

from playwright.async_api import async_playwright

import config
from parser.llm_parser import create_client, parse_list_page, parse_detail_page
from filter.matcher import filter_positions, compute_position_hash
from storage.db import Database
from notifier.email_sender import (
    format_email_subject,
    format_email_body,
    send_email,
)


async def run():
    print("=" * 50)
    print("公职招考信息聚合系统 启动")
    print("=" * 50)

    db = Database(config.DB_PATH)
    today = date.today()

    # Check LLM config
    if not config.DEEPSEEK_API_KEY:
        print("错误: DeepSeek API Key 未配置，请编辑 config.py")
        return

    llm_client = create_client(config.DEEPSEEK_API_KEY, config.DEEPSEEK_BASE_URL)

    # Step 1: Crawl list pages
    print("\n[1/5] 采集深圳考试院公告列表...")
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({"Accept-Language": "zh-CN,zh;q=0.9"})

        # Fetch list page HTML
        list_url = config.SHENZHEN_LIST_URL
        print(f"  访问: {list_url}")
        await page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(2000)
        list_html = await page.content()

        # Use LLM to extract announcement links
        print("  使用LLM解析公告列表...")
        announcements = parse_list_page(llm_client, list_html, model=config.DEEPSEEK_MODEL)
        print(f"  解析到 {len(announcements)} 条公告")

        # Fetch detail pages
        print(f"\n[2/5] 采集详情页...")
        raw_announcements = []
        for i, ann in enumerate(announcements[:20]):
            title = ann.get("title", "")[:40]
            url = ann.get("url", "")
            if not url:
                continue
            print(f"  [{i+1}/{min(len(announcements), 20)}] {title}...")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(1000)
                html = await page.content()
                raw_announcements.append({
                    "title": ann.get("title", ""),
                    "date": ann.get("date", ""),
                    "url": url,
                    "detail_html": html,
                })
            except Exception as e:
                print(f"    采集失败: {e}")

        await browser.close()

    db.log_crawl("深圳考试院", "success", len(raw_announcements))
    print(f"  采集到 {len(raw_announcements)} 个详情页")

    # Step 3: Use LLM to parse detail pages
    print(f"\n[3/5] 使用LLM解析岗位信息...")
    all_positions = []
    for i, ann in enumerate(raw_announcements):
        title = ann["title"][:40]
        print(f"  [{i+1}/{len(raw_announcements)}] {title}...")
        parsed = parse_detail_page(
            llm_client, ann["detail_html"], ann["url"], model=config.DEEPSEEK_MODEL
        )
        positions = parsed.get("positions", [])
        print(f"    → 解析出 {len(positions)} 个岗位")
        for pos in positions:
            pos["city"] = parsed.get("city", "深圳")
            pos["source_url"] = parsed.get("source_url", ann["url"])
            pos["source_name"] = parsed.get("source_name", "深圳考试院")
            pos["position_type"] = parsed.get("position_type", "事业单位")
            pos["has_establishment"] = parsed.get("has_establishment", True)
            all_positions.append(pos)

    print(f"  共解析出 {len(all_positions)} 个岗位")

    # Step 4: Filter
    print(f"\n[4/5] 筛选匹配岗位...")
    matched = filter_positions(all_positions, today, config.BIRTH_DATE)
    print(f"  匹配 {len(matched)} 个岗位")

    # Step 5: Dedup & Store
    new_positions = []
    for pos in matched:
        pos["hash"] = compute_position_hash(pos)
        if not db.hash_exists(pos["hash"]):
            db.insert_position(pos)
            new_positions.append(pos)

    print(f"  新增 {len(new_positions)} 个岗位")

    # Step 6: Notify
    print(f"\n[5/5] 发送邮件通知...")
    subject = format_email_subject(today, len(new_positions))
    body = format_email_body(new_positions, today)

    if config.SENDER_EMAIL and config.SENDER_PASSWORD and config.RECEIVER_EMAIL:
        send_email(
            {
                "smtp_host": config.SMTP_HOST,
                "smtp_port": config.SMTP_PORT,
                "sender_email": config.SENDER_EMAIL,
                "sender_password": config.SENDER_PASSWORD,
                "receiver_email": config.RECEIVER_EMAIL,
            },
            subject,
            body,
        )
    else:
        print("邮件未配置，跳过发送。以下是邮件内容：")
        print(f"\n主题: {subject}")
        print(body)

    print("\n" + "=" * 50)
    print("运行完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run())
