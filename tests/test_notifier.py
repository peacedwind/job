import pytest
from datetime import date
from notifier.email_sender import format_email_body, format_email_subject


def test_format_email_subject_with_positions():
    subject = format_email_subject(date(2026, 5, 13), 3)
    assert "2026-05-13" in subject
    assert "3" in subject
    assert "招考日报" in subject


def test_format_email_subject_zero():
    subject = format_email_subject(date(2026, 5, 13), 0)
    assert "2026-05-13" in subject


def test_format_email_body_with_positions():
    positions = [
        {
            "org": "深圳市XX局",
            "title": "信息技术岗",
            "count": 2,
            "education": "本科及以上",
            "major": "计算机科学与技术",
            "registration_start": "2026-05-15",
            "registration_end": "2026-06-01",
            "source_url": "https://example.com/1",
            "source_name": "深圳考试院",
            "position_type": "公务员",
            "has_establishment": True,
            "city": "深圳",
        }
    ]
    body = format_email_body(positions, date(2026, 5, 13))
    assert "深圳市XX局" in body
    assert "信息技术岗" in body
    assert "深圳考试院" in body
    assert "https://example.com/1" in body
    assert "有编制" in body


def test_format_email_body_empty():
    body = format_email_body([], date(2026, 5, 13))
    assert "无新增" in body


def test_format_email_body_multiple_cities():
    positions = [
        {
            "org": "深圳市XX局", "title": "技术岗", "count": 1,
            "education": "本科", "major": "计算机类",
            "registration_start": "2026-05-15", "registration_end": "2026-06-01",
            "source_url": "https://a.com", "source_name": "深圳考试院",
            "position_type": "公务员", "has_establishment": True,
            "city": "深圳",
        },
    ]
    body = format_email_body(positions, date(2026, 5, 13))
    assert "深圳" in body
