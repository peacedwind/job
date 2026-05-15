import asyncio
from datetime import date, timedelta

from playwright.async_api import async_playwright

import config
from parser.llm_parser import (
    create_client,
    parse_list_page,
    analyze_detail_page,
    parse_attachment_text,
)
from parser.attachment_parser import process_attachment, should_download
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

    if not config.DEEPSEEK_API_KEY:
        print("错误: DeepSeek API Key 未配置，请编辑 config.py")
        return

    llm = create_client(config.DEEPSEEK_API_KEY, config.DEEPSEEK_BASE_URL)
    model = config.DEEPSEEK_MODEL

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_extra_http_headers({"Accept-Language": "zh-CN,zh;q=0.9"})

        all_positions = []

        for source in config.DATA_SOURCES:
            source_name = source["name"]
            list_url = source["list_url"]

            # === 第1层: 列表页 ===
            print(f"\n{'='*40}")
            print(f"[数据源] {source_name}")
            print(f"  URL: {list_url}")
            print(f"{'='*40}")

            try:
                await page.goto(list_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
                list_html = await page.content()
            except Exception as e:
                print(f"  列表页采集失败: {e}")
                db.log_crawl(source_name, "failed", error_message=str(e))
                continue

            print("  LLM解析公告列表...")
            announcements = parse_list_page(llm, list_html, model=model)
            print(f"  解析到 {len(announcements)} 条公告")

            # Filter by date
            if config.MAX_ANNOUNCEMENT_DAYS > 0:
                cutoff = today - timedelta(days=config.MAX_ANNOUNCEMENT_DAYS)
                original_count = len(announcements)
                announcements = [
                    ann for ann in announcements
                    if _is_recent(ann.get("date", ""), cutoff)
                ]
                print(f"  过滤后保留 {len(announcements)} 条（{config.MAX_ANNOUNCEMENT_DAYS}天内）")

            # === 第2层: 详情页 ===
            for i, ann in enumerate(announcements[:20]):
                title = ann.get("title", "")[:40]
                url = ann.get("url", "")
                if not url:
                    continue
                print(f"\n  [{i+1}/{min(len(announcements), 20)}] {title}")

                # Fetch detail page
                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(1000)
                    html = await page.content()
                except Exception as e:
                    print(f"    采集失败: {e}")
                    continue

                # LLM analyzes and decides action
                decision = analyze_detail_page(llm, html, url, model=model)
                action = decision.get("action", "skip")
                reason = decision.get("reason", "")
                # Override source_name from config
                decision["source_name"] = source_name
                print(f"    决策: {action} - {reason}")

                if action == "extract":
                    positions = decision.get("positions", [])
                    print(f"    → 提取到 {len(positions)} 个岗位")
                    _attach_metadata(positions, decision)
                    all_positions.extend(positions)

                elif action == "download":
                    attachments = decision.get("attachments", [])
                    for att in attachments:
                        att_url = att.get("url", "")
                        att_type = att.get("type", "unknown")
                        att_context = att.get("context", "")
                        if not should_download(att_url, att_context):
                            print(f"    跳过附件(不相关): {att_url.split('/')[-1][:40]}")
                            continue
                        print(f"    下载附件: {att_type} {att_url[:60]}...")
                        text = await process_attachment(att_url)
                        if text:
                            print(f"    附件文本: {len(text)} 字符")
                            att_result = parse_attachment_text(llm, text, att_url, model=model)
                            positions = att_result.get("positions", [])
                            print(f"    → 附件解析出 {len(positions)} 个岗位")
                            _attach_metadata(positions, decision)
                            all_positions.extend(positions)
                        else:
                            print(f"    附件下载/解析失败")

                elif action == "follow":
                    links = decision.get("links", [])
                    for link in links[:3]:
                        link_url = link.get("url", "")
                        print(f"    跟踪链接: {link_url[:60]}...")
                        try:
                            await page.goto(link_url, wait_until="domcontentloaded", timeout=30000)
                            await page.wait_for_timeout(1000)
                            link_html = await page.content()

                            link_decision = analyze_detail_page(llm, link_html, link_url, model=model)
                            link_decision["source_name"] = source_name
                            link_action = link_decision.get("action", "skip")
                            print(f"    链接页决策: {link_action}")

                            if link_action == "extract":
                                positions = link_decision.get("positions", [])
                                print(f"    → 链接页提取到 {len(positions)} 个岗位")
                                _attach_metadata(positions, link_decision)
                                all_positions.extend(positions)
                            elif link_action == "download":
                                for att in link_decision.get("attachments", []):
                                    att_url = att.get("url", "")
                                    att_context = att.get("context", "")
                                    if not should_download(att_url, att_context):
                                        print(f"    跳过附件(不相关): {att_url.split('/')[-1][:40]}")
                                        continue
                                    print(f"    下载链接页附件: {att_url[:60]}...")
                                    text = await process_attachment(att_url)
                                    if text:
                                        att_result = parse_attachment_text(llm, text, att_url, model=model)
                                        positions = att_result.get("positions", [])
                                        print(f"    → 附件解析出 {len(positions)} 个岗位")
                                        _attach_metadata(positions, link_decision)
                                        all_positions.extend(positions)
                        except Exception as e:
                            print(f"    链接采集失败: {e}")

                elif action == "skip":
                    print(f"    跳过")

            db.log_crawl(source_name, "success", len(announcements))

        await browser.close()

    print(f"\n共解析出 {len(all_positions)} 个岗位")

    # === 筛选 ===
    print(f"\n[筛选] 匹配岗位...")
    matched = filter_positions(all_positions, today, config.BIRTH_DATE)
    print(f"  匹配 {len(matched)} 个岗位")

    # === 去重存储 ===
    new_positions = []
    for pos in matched:
        pos["hash"] = compute_position_hash(pos)
        if not db.hash_exists(pos["hash"]):
            db.insert_position(pos)
            new_positions.append(pos)
    print(f"  新增 {len(new_positions)} 个岗位")

    # === 邮件通知 ===
    print(f"\n[通知] 发送邮件...")
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


def _attach_metadata(positions: list[dict], decision: dict):
    """Attach common metadata to positions from the decision."""
    for pos in positions:
        pos.setdefault("city", decision.get("city", "深圳"))
        pos.setdefault("source_url", decision.get("source_url", ""))
        pos.setdefault("source_name", decision.get("source_name", "深圳考试院"))
        pos.setdefault("position_type", decision.get("position_type", "事业单位"))
        pos.setdefault("has_establishment", decision.get("has_establishment", True))


def _is_recent(date_str: str, cutoff: date) -> bool:
    """Check if a date string is within the cutoff range.
    Accepts formats: YYYY-MM-DD, YYYY/MM/DD, YYYY年M月D日.
    Returns True if date is missing/unparseable (be permissive).
    """
    if not date_str:
        return True
    try:
        # Try YYYY-MM-DD
        d = date.fromisoformat(date_str.strip())
        return d >= cutoff
    except ValueError:
        pass
    try:
        # Try YYYY/MM/DD
        parts = date_str.strip().replace("/", "-").split("-")
        if len(parts) == 3:
            d = date(int(parts[0]), int(parts[1]), int(parts[2]))
            return d >= cutoff
    except (ValueError, IndexError):
        pass
    # Can't parse - be permissive
    return True


if __name__ == "__main__":
    asyncio.run(run())
