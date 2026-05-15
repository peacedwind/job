import hashlib
import re
from datetime import date


MAJOR_KEYWORDS = ["计算机", "软件工程", "信息技术", "信息管理"]
EDUCATION_RANK = {
    "高中": 1, "中专": 1,
    "大专": 2, "专科": 2,
    "本科": 3, "学士": 3, "大学": 3,
    "硕士研究生": 4, "硕士": 4, "研究生": 4,
    "博士研究生": 5, "博士": 5,
}
TARGET_EDUCATION_RANK = 3  # 本科


def filter_positions(
    positions: list[dict],
    today: date,
    birth_date: date,
    target_cities: list[str] | None = None,
) -> list[dict]:
    """Apply all hard filters and return matching positions."""
    if target_cities is None:
        target_cities = ["深圳"]

    current_age = _calculate_age(birth_date, today)

    results = []
    for pos in positions:
        if not _check_establishment(pos):
            continue
        if not _check_city(pos, target_cities):
            continue
        if not _check_education(pos):
            continue
        if not _check_major(pos):
            continue
        if not _check_political(pos):
            continue
        if not _check_age(pos, current_age, birth_date):
            continue
        if not _check_timeliness(pos, today):
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
    return pos.get("has_establishment", False) is True


def _check_city(pos: dict, target_cities: list[str]) -> bool:
    return pos.get("city", "") in target_cities


def _check_education(pos: dict) -> bool:
    """Position education requirement must be <= target (本科)."""
    edu = pos.get("education", "")
    for keyword, rank in EDUCATION_RANK.items():
        if keyword in edu:
            return rank <= TARGET_EDUCATION_RANK
    # If we can't determine, be permissive
    return True


def _check_major(pos: dict) -> bool:
    """Position major must contain at least one target keyword."""
    major = pos.get("major", "")
    if not major:
        return True  # No major requirement = any major OK
    return any(kw in major for kw in MAJOR_KEYWORDS)


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
