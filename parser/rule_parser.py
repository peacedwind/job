import re
from bs4 import BeautifulSoup


def parse_position_table(html: str) -> list[dict]:
    """Extract position rows from an HTML table."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    # Detect header row to map column indices
    headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    col_map = _build_column_map(headers)

    positions = []
    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 3:
            continue
        pos = _extract_position(cells, col_map)
        if pos:
            positions.append(pos)

    return positions


def _build_column_map(headers: list[str]) -> dict[str, int]:
    """Map Chinese header names to column indices."""
    mapping = {}
    keywords = {
        "org": ["招录单位", "用人单位", "招聘单位", "单位"],
        "title": ["岗位名称", "职位名称", "岗位", "职位"],
        "count": ["招录人数", "招聘人数", "人数", "计划数"],
        "education": ["学历", "学历要求", "最低学历"],
        "major": ["专业", "专业要求"],
        "age_limit": ["年龄", "年龄要求"],
        "political_requirement": ["政治面貌", "政治面貌要求"],
    }
    for i, header in enumerate(headers):
        for field, kws in keywords.items():
            if any(kw in header for kw in kws):
                mapping[field] = i
                break
    return mapping


def _extract_position(cells: list[str], col_map: dict[str, int]) -> dict | None:
    """Extract a position dict from table cells."""
    def get(field):
        idx = col_map.get(field)
        if idx is not None and idx < len(cells):
            return cells[idx]
        return None

    org = get("org")
    title = get("title")
    if not org and not title:
        return None

    count_str = get("count") or "1"
    count = int(re.search(r"\d+", count_str).group()) if re.search(r"\d+", count_str) else 1

    return {
        "org": org or "",
        "title": title or "",
        "count": count,
        "education": get("education") or "",
        "major": get("major") or "",
        "age_limit": get("age_limit") or "",
        "political_requirement": get("political_requirement") or "不限",
        "registration_start": None,
        "registration_end": None,
    }


def parse_detail_page(html: str, url: str) -> dict:
    """Parse a detail page into structured announcement data."""
    soup = BeautifulSoup(html, "lxml")

    # Extract title
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    # Extract positions from tables
    positions = parse_position_table(html)

    # Extract registration dates from surrounding text
    full_text = soup.get_text()
    dates = _extract_registration_dates(full_text)
    for pos in positions:
        pos["registration_start"] = dates.get("start")
        pos["registration_end"] = dates.get("end")

    return {
        "title": title,
        "city": "深圳",
        "source_url": url,
        "source_name": "深圳考试院",
        "publish_date": None,
        "position_type": _detect_position_type(title),
        "has_establishment": _detect_establishment(full_text),
        "positions": positions,
    }


def _extract_registration_dates(text: str) -> dict[str, str | None]:
    """Extract registration start/end dates from text."""
    result = {"start": None, "end": None}

    # Try YYYY年M月D日至YYYY年M月D日
    match = re.search(
        r"报名[时时间].*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日.*?[至到~-].*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        text,
    )
    if match:
        y1, m1, d1 = match.group(1), match.group(2).zfill(2), match.group(3).zfill(2)
        y2, m2, d2 = match.group(4), match.group(5).zfill(2), match.group(6).zfill(2)
        result["start"] = f"{y1}-{m1}-{d1}"
        result["end"] = f"{y2}-{m2}-{d2}"
        return result

    # Try YYYY-MM-DD format
    match = re.search(
        r"报名.*?(\d{4}-\d{2}-\d{2}).*?[至到~-].*?(\d{4}-\d{2}-\d{2})",
        text,
    )
    if match:
        result["start"] = match.group(1)
        result["end"] = match.group(2)

    return result


def _detect_position_type(title: str) -> str:
    """Detect position type from title."""
    if "公务员" in title:
        return "公务员"
    if "教师" in title or "教育" in title:
        return "小学教师"
    return "事业单位"


def _detect_establishment(text: str) -> bool:
    """Detect if the announcement mentions 事业编制 or 公务员编制."""
    keywords = ["事业编制", "公务员编制", "有编制", "在编", "编制内"]
    negative = ["编外", "合同制", "劳务派遣", "非编制"]
    for kw in negative:
        if kw in text:
            return False
    for kw in keywords:
        if kw in text:
            return True
    # Default to True for government announcements (conservative)
    return True
