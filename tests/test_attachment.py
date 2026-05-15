import pytest
from parser.attachment_parser import should_download


def test_download_position_table():
    """岗位表 should be downloaded."""
    assert should_download("https://example.com/岗位表.xlsx", "") is True


def test_download_recruitment_plan():
    """招聘计划表 should be downloaded."""
    assert should_download("https://example.com/recruitment.pdf", "2026年招聘计划表") is True


def test_download_position_list():
    """职位表 should be downloaded."""
    assert should_download("https://example.com/pos.xlsx", "职位一览表") is True


def test_skip_commitment_letter():
    """承诺书 should be skipped."""
    assert should_download("https://example.com/承诺书.pdf", "") is False


def test_skip_notice():
    """报名须知 should be skipped."""
    assert should_download("https://example.com/guide.pdf", "报名须知") is False


def test_skip_unknown():
    """Unknown attachments should be skipped."""
    assert should_download("https://example.com/file123.pdf", "") is False


def test_context_keyword_match():
    """Context containing position keywords should trigger download."""
    assert should_download("https://example.com/abc.xlsx", "附件：岗位需求表") is True


def test_exclude_overrides_include():
    """Exclude keywords should take priority."""
    assert should_download("https://example.com/岗位报名须知.pdf", "") is False
