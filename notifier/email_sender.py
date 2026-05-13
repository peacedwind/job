import smtplib
from datetime import date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def format_email_subject(day: date, count: int) -> str:
    return f"[招考日报] {day.isoformat()} 新增 {count} 个匹配岗位"


def format_email_body(positions: list[dict], today: date) -> str:
    if not positions:
        return (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"今日无新增匹配岗位\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    city_groups: dict[str, list[dict]] = {}
    for pos in positions:
        city = pos.get("city", "其他")
        city_groups.setdefault(city, []).append(pos)

    city_icons = {"深圳": "🔴", "杭州": "🟡", "武汉": "🟢"}

    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", ""]
    idx = 1

    for city in ["深圳", "杭州", "武汉"]:
        icon = city_icons.get(city, "⚪")
        city_positions = city_groups.get(city, [])
        lines.append(f"{icon} {city} ({len(city_positions)}个)")
        lines.append("")

        if not city_positions:
            lines.append("   今日无新增匹配岗位")
            lines.append("")
            continue

        for pos in city_positions:
            est_text = "(有编制)" if pos.get("has_establishment") else "(无编制)"
            lines.append(f"{idx}. {pos['org']} - {pos['title']} {est_text}")
            lines.append(f"   类型：{pos.get('position_type', '未知')}")
            lines.append(
                f"   招录：{pos.get('count', 1)}人 | {pos['education']} | {pos['major']}"
            )
            lines.append(f"   报名：{pos.get('registration_start', '未知')} 至 {pos.get('registration_end', '未知')}")
            lines.append(f"   来源：{pos.get('source_name', '未知')}")
            lines.append(f"   链接：{pos['source_url']}")
            lines.append("")
            idx += 1

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⏰ 近期时间节点提醒 (未来7天)")
    reminders = _collect_reminders(positions, today)
    if reminders:
        for rem in reminders:
            lines.append(f"   - {rem}")
    else:
        lines.append("   无近期时间节点")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def _collect_reminders(positions: list[dict], today: date) -> list[str]:
    """Collect registration start/end dates within next 7 days."""
    reminders = []
    cutoff = today + timedelta(days=7)

    for pos in positions:
        start = pos.get("registration_start")
        end = pos.get("registration_end")
        org = pos.get("org", "")
        title = pos.get("title", "")

        if start:
            try:
                start_date = date.fromisoformat(start)
                if today <= start_date <= cutoff:
                    reminders.append(f"{start} {org} {title} 报名开始")
            except ValueError:
                pass

        if end:
            try:
                end_date = date.fromisoformat(end)
                if today <= end_date <= cutoff:
                    reminders.append(f"{end} {org} {title} 报名截止")
            except ValueError:
                pass

    reminders.sort()
    return reminders


def send_email(config: dict, subject: str, body: str) -> bool:
    """Send email via QQ SMTP. Returns True on success."""
    try:
        msg = MIMEMultipart()
        msg["From"] = config["sender_email"]
        msg["To"] = config["receiver_email"]
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL(config["smtp_host"], config["smtp_port"]) as server:
            server.login(config["sender_email"], config["sender_password"])
            server.send_message(msg)

        print(f"Email sent to {config['receiver_email']}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
