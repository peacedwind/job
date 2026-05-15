import pytest
from datetime import date
from filter.matcher import filter_positions, compute_position_hash


@pytest.fixture
def sample_position():
    """A position that passes all filters."""
    return {
        "org": "深圳市XX局",
        "title": "信息技术岗",
        "count": 2,
        "education": "本科及以上",
        "major": "计算机科学与技术",
        "age_limit": "35周岁以下",
        "political_requirement": "不限",
        "registration_end": "2026-12-31",
        "has_establishment": True,
        "city": "深圳",
        "source_url": "https://example.com/1",
        "position_type": "公务员",
    }


def test_passes_all_filters(sample_position):
    """A valid position should pass all filters."""
    today = date(2026, 5, 13)
    birth_date = date(1992, 11, 24)
    result = filter_positions([sample_position], today, birth_date)
    assert len(result) == 1


def test_filter_no_establishment(sample_position):
    """Positions without establishment should be filtered out."""
    sample_position["has_establishment"] = False
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_wrong_city(sample_position):
    """Positions in non-target cities should be filtered out."""
    sample_position["city"] = "北京"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_education_too_high(sample_position):
    """Positions requiring education above target should be filtered out."""
    sample_position["education"] = "硕士及以上"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_unrelated_major(sample_position):
    """Positions with unrelated majors should be filtered out."""
    sample_position["major"] = "法学、行政管理"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_political_requirement(sample_position):
    """Positions requiring party membership should be filtered out."""
    sample_position["political_requirement"] = "中共党员"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_expired_registration(sample_position):
    """Positions with expired registration should be filtered out."""
    sample_position["registration_end"] = "2026-01-01"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_age_too_old(sample_position):
    """Positions with age limit too low should be filtered out."""
    sample_position["age_limit"] = "30周岁以下"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_age_birth_after_format(sample_position):
    """Should handle 'XXXX年X月X日以后出生' format."""
    sample_position["age_limit"] = "1991年1月1日以后出生"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 1


def test_filter_multiple_positions(sample_position):
    """Should filter a list of mixed positions correctly."""
    pos2 = sample_position.copy()
    pos2["title"] = "管理岗"
    pos2["major"] = "法学"
    pos2["source_url"] = "https://example.com/2"

    today = date(2026, 5, 13)
    result = filter_positions([sample_position, pos2], today, date(1992, 11, 24))
    assert len(result) == 1
    assert result[0]["title"] == "信息技术岗"


def test_education_bachelor_accepted(sample_position):
    """本科 should be accepted."""
    sample_position["education"] = "本科"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 1


def test_major_partial_match(sample_position):
    """Should match partial major keywords like '计算机'."""
    sample_position["major"] = "计算机类"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 1


def test_hash_deterministic():
    pos = {"source_url": "https://a.com", "title": "技术岗", "org": "XX局"}
    h1 = compute_position_hash(pos)
    h2 = compute_position_hash(pos)
    assert h1 == h2


def test_hash_different_for_different_positions():
    pos1 = {"source_url": "https://a.com", "title": "技术岗", "org": "XX局"}
    pos2 = {"source_url": "https://b.com", "title": "管理岗", "org": "YY局"}
    assert compute_position_hash(pos1) != compute_position_hash(pos2)


def test_education_bachelor_synonym(sample_position):
    """学士 should be accepted (same as 本科)."""
    sample_position["education"] = "学士学位"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 1


def test_education_research_student(sample_position):
    """研究生 should be rejected (rank > 本科)."""
    sample_position["education"] = "研究生"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_education_master_research_student(sample_position):
    """硕士研究生 should be rejected."""
    sample_position["education"] = "硕士研究生"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_education_university(sample_position):
    """大学 should be accepted (same as 本科)."""
    sample_position["education"] = "大学本科"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 1
