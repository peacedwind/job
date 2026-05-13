import asyncio
from datetime import date

import config
from crawler.shenzhen import crawl_shenzhen
from parser.rule_parser import parse_detail_page
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

    # Step 1: Crawl
    print("\n[1/5] 采集深圳考试院公告...")
    try:
        raw_announcements = await crawl_shenzhen({
            "list_url": config.SHENZHEN_LIST_URL,
            "max_pages": 3,
        })
        db.log_crawl("深圳考试院", "success", len(raw_announcements))
    except Exception as e:
        print(f"采集失败: {e}")
        db.log_crawl("深圳考试院", "failed", error_message=str(e))
        raw_announcements = []

    print(f"采集到 {len(raw_announcements)} 条公告")

    # Step 2: Parse
    print("\n[2/5] 解析公告内容...")
    all_positions = []
    for ann in raw_announcements:
        parsed = parse_detail_page(ann["detail_html"], ann["url"])
        for pos in parsed["positions"]:
            pos["city"] = parsed["city"]
            pos["source_url"] = parsed["source_url"]
            pos["source_name"] = parsed["source_name"]
            pos["position_type"] = parsed["position_type"]
            pos["has_establishment"] = parsed["has_establishment"]
            all_positions.append(pos)

    print(f"解析出 {len(all_positions)} 个岗位")

    # Step 3: Filter
    print("\n[3/5] 筛选匹配岗位...")
    matched = filter_positions(all_positions, today, config.BIRTH_DATE)
    print(f"匹配 {len(matched)} 个岗位")

    # Step 4: Dedup & Store
    print("\n[4/5] 去重并存储...")
    new_positions = []
    for pos in matched:
        pos["hash"] = compute_position_hash(pos)
        if not db.hash_exists(pos["hash"]):
            db.insert_position(pos)
            new_positions.append(pos)

    print(f"新增 {len(new_positions)} 个岗位")

    # Step 5: Notify
    print("\n[5/5] 发送邮件通知...")
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
