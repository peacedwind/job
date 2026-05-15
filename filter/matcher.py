import hashlib
import re
from datetime import date

import config


MAJOR_KEYWORDS_MAP = {
    "计算机科学与技术": "计算机",
    "软件工程": "软件工程",
    "信息技术": "信息技术",
    "计算机类": "计算机",
    "文学": "文学",
    "信息管理": "信息管理",
}
EDUCATION_RANK = {
    "高中": 1, "中专": 1,
    "大专": 2, "专科": 2,
    "本科": 3, "学士": 3, "大学": 3,
    "硕士研究生": 4, "硕士": 4, "研究生": 4,
    "博士研究生": 5, "博士": 5,
}


def _get_major_keywords() -> list[str]:
    """Derive search keywords from config.MAJOR_KEYWORDS."""
    keywords = []
    for major in config.MAJORS:
        if major in MAJOR_KEYWORDS_MAP:
            keywords.append(MAJOR_KEYWORDS_MAP[major])
        else:
            keywords.append(major)
    return keywords


def _get_target_education_rank() -> int:
    """Get education rank from config.EDUCATION."""
    edu = config.EDUCATION
    for keyword, rank in EDUCATION_RANK.items():
        if keyword in edu:
            return rank
    return 4  # Default to 硕士


def filter_positions(
    positions: list[dict],
    today: date,
    birth_date: date,
    target_cities: list[str] | None = None,
) -> list[dict]:
    """Apply all hard filters and return matching positions."""
    if target_cities is None:
        target_cities = config.CITIES

    current_age = _calculate_age(birth_date, today)

    results = []
    for pos in positions:
        title = pos.get("title", "?")[:30]
        if not _check_establishment(pos):
            print(f"    [X] 编制不符: {title}")
            continue
        if not _check_city(pos, target_cities):
            print(f"    [X] 城市不符: {title} (城市={pos.get('city', '?')})")
            continue
        if not _check_education(pos):
            print(f"    [X] 学历不符: {title} (要求={pos.get('education', '?')})")
            continue
        if not _check_major(pos):
            print(f"    [X] 专业不符: {title} (专业={pos.get('major', '?')})")
            continue
        if not _check_political(pos):
            print(f"    [X] 政治面貌不符: {title}")
            continue
        if not _check_age(pos, current_age, birth_date):
            print(f"    [X] 年龄不符: {title} (年龄限制={pos.get('age_limit', '?')})")
            continue
        if not _check_timeliness(pos, today):
            print(f"    [X] 已过期: {title} (截止={pos.get('registration_end', '?')})")
            continue
        results.append(pos)

    return results


def compute_position_hash(position: dict) -> str:
    """Compute a unique hash for a position based on source_url + title + org."""
    key = f"{position.get('source_url', '')}{position.get('title', '')}{position.get('org', '')}"
    return hashlib.md5(key.encode()).hexdigest()


def _calculate_age(birth_date: date, today: date) -> int:
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def _check_establishment(pos: dict) -> bool:
    return bool(pos.get("has_establishment", False))


def _check_city(pos: dict, target_cities: list[str]) -> bool:
    """Check city by looking at position's org, title, and city field."""
    # Combine all text fields that might contain city info
    searchable = " ".join([
        pos.get("city", ""),
        pos.get("org", ""),
        pos.get("title", ""),
        pos.get("source_name", ""),
    ])
    return any(city in searchable for city in target_cities)


def _check_education(pos: dict) -> bool:
    """Position education requirement must be <= target."""
    target_rank = _get_target_education_rank()
    # Use pre-computed education_level from DB if available
    pos_level = pos.get("education_level")
    if pos_level is not None:
        return int(pos_level) <= target_rank
    # Fallback to text matching
    edu = pos.get("education", "")
    for keyword, rank in EDUCATION_RANK.items():
        if keyword in edu:
            return rank <= target_rank
    return True


def _check_major(pos: dict) -> bool:
    """Position major must contain at least one target keyword."""
    major = pos.get("major", "")
    # 无专业要求的情况：空、无、无限制、不限等
    major = major.strip()
    if not major or major in ("无", "无限制", "不限", "—", "-", "/"):
        return True
    keywords = _get_major_keywords()
    return any(kw in major for kw in keywords)


def _check_political(pos: dict) -> bool:
    """Exclude positions requiring party membership."""
    req = pos.get("political_requirement", "不限")
    if not req or req in ("不限", "无", ""):
        return True
    # Reject if it requires party membership
    party_keywords = ["党员", "预备党员", "中共党员"]
    return not any(kw in req for kw in party_keywords)


def _check_age(pos: dict, current_age: int, birth_date: date) -> bool:
    """Check if age meets the position requirement."""
    age_limit = pos.get("age_limit", "")
    if not age_limit:
        return True  # No age requirement

    # Pattern: "XX周岁以下"
    match = re.search(r"(\d+)\s*周岁以下", age_limit)
    if match:
        max_age = int(match.group(1))
        return current_age <= max_age

    # Pattern: "XXXX年X月X日以后出生"
    match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日以后出生", age_limit)
    if match:
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        cutoff = date(y, m, d)
        return birth_date >= cutoff

    # Pattern: "XX岁以下"
    match = re.search(r"(\d+)\s*岁以下", age_limit)
    if match:
        max_age = int(match.group(1))
        return current_age <= max_age

    # Can't parse, be permissive
    return True


def _check_timeliness(pos: dict, today: date) -> bool:
    """Check registration hasn't expired."""
    end = pos.get("registration_end")
    if not end:
        return True  # No end date = assume active
    try:
        end_date = date.fromisoformat(end)
        return end_date >= today
    except ValueError:
        return True  # Can't parse = be permissive
