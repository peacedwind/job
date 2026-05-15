import asyncio
import hashlib
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


def _url_hash(url: str) -> str:
    return hashlib.md5(url.encode()).hexdigest()


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

        for source in config.DATA_SOURCES:
            source_name = source["name"]
            list_url = source["list_url"]
            new_count = 0
            skipped = 0

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
                db.update_source_state(source_name, success=False)
                continue

            print("  LLM解析公告列表...")
            announcements = parse_list_page(llm, list_html, model=model)
            announcements.sort(key=lambda x: x.get("date", ""), reverse=True)
            print(f"  解析到 {len(announcements)} 条公告")

            # Filter by date
            if config.MAX_ANNOUNCEMENT_DAYS > 0:
                cutoff = today - timedelta(days=config.MAX_ANNOUNCEMENT_DAYS)
                announcements = [
                    ann for ann in announcements
                    if _is_recent(ann.get("date", ""), cutoff)
                ]
                print(f"  过滤后保留 {len(announcements)} 条（{config.MAX_ANNOUNCEMENT_DAYS}天内）")

            # === 增量处理：逐个公告，遇到已见过的就 break ===
            for i, ann in enumerate(announcements[:20]):
                title = ann.get("title", "")[:40]
                url = ann.get("url", "")
                if not url:
                    continue

                url_hash_val = _url_hash(url)

                # 检查是否已处理过
                if db.announcement_seen(url_hash_val):
                    print(f"  [{i+1}] 已见过: {title}，停止该数据源")
                    skipped = len(announcements[:20]) - i
                    break

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
                decision["source_name"] = source_name
                print(f"    决策: {action} - {reason}")

                has_positions = False

                if action == "extract":
                    positions = decision.get("positions", [])
                    if positions:
                        has_positions = True
                        print(f"    → 提取到 {len(positions)} 个岗位")
                        _attach_metadata(positions, decision)
                        _store_positions(db, positions, url_hash_val, source_name)
                        new_count += len(positions)

                elif action == "download":
                    attachments = decision.get("attachments", [])
                    for att in attachments:
                        att_url = att.get("url", "")
                        att_context = att.get("context", "")
                        if not should_download(att_url, att_context):
                            print(f"    跳过附件(不相关): {att_url.split('/')[-1][:40]}")
                            continue
                        print(f"    下载附件: {att_url[:60]}...")
                        text = await process_attachment(att_url, page=page)
                        if text:
                            print(f"    附件文本: {len(text)} 字符")
                            att_result = parse_attachment_text(llm, text, att_url, model=model)
                            positions = att_result.get("positions", [])
                            if positions:
                                has_positions = True
                                print(f"    → 附件解析出 {len(positions)} 个岗位")
                                _attach_metadata(positions, decision)
                                _store_positions(db, positions, url_hash_val, source_name)
                                new_count += len(positions)
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
                                if positions:
                                    has_positions = True
                                    print(f"    → 链接页提取到 {len(positions)} 个岗位")
                                    _attach_metadata(positions, link_decision)
                                    _store_positions(db, positions, url_hash_val, source_name)
                                    new_count += len(positions)
                            elif link_action == "download":
                                for att in link_decision.get("attachments", []):
                                    att_url = att.get("url", "")
                                    att_context = att.get("context", "")
                                    if not should_download(att_url, att_context):
                                        print(f"    跳过附件(不相关): {att_url.split('/')[-1][:40]}")
                                        continue
                                    print(f"    下载链接页附件: {att_url[:60]}...")
                                    text = await process_attachment(att_url, page=page)
                                    if text:
                                        att_result = parse_attachment_text(llm, text, att_url, model=model)
                                        positions = att_result.get("positions", [])
                                        if positions:
                                            has_positions = True
                                            print(f"    → 附件解析出 {len(positions)} 个岗位")
                                            _attach_metadata(positions, link_decision)
                                            _store_positions(db, positions, url_hash_val, source_name)
                                            new_count += len(positions)
                        except Exception as e:
                            print(f"    链接采集失败: {e}")

                elif action == "skip":
                    print(f"    跳过")

                # 无论有无岗位，都标记为已见过
                db.mark_announcement_seen(url_hash_val, source_name, title, has_positions)

            if skipped > 0:
                print(f"  跳过 {skipped} 条已见过的公告")

            db.log_crawl(source_name, "success", new_count)
            db.update_source_state(source_name, success=True)

        await browser.close()

    # === 从 DB 查询未通知岗位 → 筛选 → 邮件 ===
    receiver = config.RECEIVER_EMAIL
    print(f"\n[筛选] 从数据库查询未通知岗位（收件人: {receiver}）...")
    unnotified = db.get_unnotified_positions(receiver)
    print(f"  未通知岗位: {len(unnotified)} 个")

    print(f"  筛选匹配岗位...")
    matched = filter_positions(unnotified, today, config.BIRTH_DATE)
    print(f"  匹配 {len(matched)} 个岗位")

    # === 邮件通知 ===
    print(f"\n[通知] 发送邮件...")
    subject = format_email_subject(today, len(matched))
    body = format_email_body(matched, today)

    if config.SENDER_EMAIL and config.SENDER_PASSWORD and receiver:
        send_email(
            {
                "smtp_host": config.SMTP_HOST,
                "smtp_port": config.SMTP_PORT,
                "sender_email": config.SENDER_EMAIL,
                "sender_password": config.SENDER_PASSWORD,
                "receiver_email": receiver,
            },
            subject,
            body,
        )
    else:
        print("邮件未配置，跳过发送。以下是邮件内容：")
        print(f"\n主题: {subject}")
        print(body)

    # 标记已通知
    if matched:
        db.mark_notified([pos["id"] for pos in matched], receiver)

    print("\n" + "=" * 50)
    print("运行完成")
    print("=" * 50)


def _store_positions(db: Database, positions: list[dict],
                      url_hash_val: str, source_name: str):
    """Store positions to DB immediately."""
    for pos in positions:
        pos["hash"] = compute_position_hash(pos)
        pos["url_hash"] = url_hash_val
        pos.setdefault("source_name", source_name)
        db.insert_position(pos)


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
        d = date.fromisoformat(date_str.strip())
        return d >= cutoff
    except ValueError:
        pass
    try:
        parts = date_str.strip().replace("/", "-").split("-")
        if len(parts) == 3:
            d = date(int(parts[0]), int(parts[1]), int(parts[2]))
            return d >= cutoff
    except (ValueError, IndexError):
        pass
    return True


if __name__ == "__main__":
    asyncio.run(run())
