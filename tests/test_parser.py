import pytest
from parser.rule_parser import parse_detail_page, parse_position_table


SAMPLE_TABLE_HTML = """
<div class="content">
<table>
<thead>
<tr><th>招录单位</th><th>岗位名称</th><th>招录人数</th><th>学历</th><th>专业</th><th>年龄</th><th>政治面貌</th></tr>
</thead>
<tbody>
<tr><td>深圳市XX局</td><td>信息技术岗</td><td>2</td><td>本科及以上</td><td>计算机科学与技术、软件工程</td><td>35周岁以下</td><td>不限</td></tr>
<tr><td>深圳市YY局</td><td>综合管理岗</td><td>1</td><td>硕士及以上</td><td>行政管理</td><td>30周岁以下</td><td>中共党员</td></tr>
</tbody>
</table>
<p>报名时间：2026年5月15日至2026年6月1日</p>
</div>
"""

SAMPLE_ANNOUNCEMENT_HTML = """
<div class="article">
<h1>2026年深圳市XX局公务员招录公告</h1>
<p>根据公务员法和公务员录用规定...</p>
{table_content}
<p>本公告由深圳市XX局负责解释。</p>
</div>
""".format(table_content=SAMPLE_TABLE_HTML)


def test_parse_position_table_extracts_rows():
    """Should extract all position rows from a table."""
    positions = parse_position_table(SAMPLE_TABLE_HTML)
    assert len(positions) == 2


def test_parse_position_table_first_row():
    """First row should have correct field values."""
    positions = parse_position_table(SAMPLE_TABLE_HTML)
    pos = positions[0]
    assert pos["org"] == "深圳市XX局"
    assert pos["title"] == "信息技术岗"
    assert pos["count"] == 2
    assert pos["education"] == "本科及以上"
    assert pos["major"] == "计算机科学与技术、软件工程"
    assert pos["age_limit"] == "35周岁以下"
    assert pos["political_requirement"] == "不限"


def test_parse_position_table_major_variations():
    """Should handle different major field formats."""
    html = """
    <table>
    <tr><th>单位</th><th>岗位</th><th>人数</th><th>学历</th><th>专业</th><th>年龄</th><th>政治面貌</th></tr>
    <tr><td>某单位</td><td>技术岗</td><td>1</td><td>本科</td><td>计算机类</td><td>40岁以下</td><td>无</td></tr>
    </table>
    """
    positions = parse_position_table(html)
    assert positions[0]["major"] == "计算机类"
    assert positions[0]["political_requirement"] == "无"


def test_parse_detail_page_extracts_metadata():
    """Should extract title, publish_date, and positions from a full page."""
    result = parse_detail_page(SAMPLE_ANNOUNCEMENT_HTML, "https://example.com/1")
    assert result["title"] == "2026年深圳市XX局公务员招录公告"
    assert result["source_url"] == "https://example.com/1"
    assert result["city"] == "深圳"
    assert len(result["positions"]) == 2


def test_parse_detail_page_registration_dates():
    """Should extract registration start and end dates."""
    result = parse_detail_page(SAMPLE_ANNOUNCEMENT_HTML, "https://example.com/1")
    pos = result["positions"][0]
    assert pos["registration_start"] == "2026-05-15"
    assert pos["registration_end"] == "2026-06-01"


def test_parse_no_table_returns_empty():
    """Page with no table should return empty positions list."""
    html = "<div><p>No positions here</p></div>"
    result = parse_detail_page(html, "https://example.com/2")
    assert result["positions"] == []
