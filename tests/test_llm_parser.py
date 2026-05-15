import pytest
import json


def test_json_extraction_from_markdown():
    """LLM parser should extract JSON from markdown code blocks."""
    content = '''```json
[{"title": "test", "date": "2026-05-10", "url": "https://example.com"}]
```'''
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    result = json.loads(content)
    assert len(result) == 1
    assert result[0]["title"] == "test"


def test_json_extraction_plain():
    """Should parse plain JSON directly."""
    content = '[{"title": "test"}]'
    result = json.loads(content)
    assert result[0]["title"] == "test"


def test_json_extraction_extract_action():
    """Should parse extract action format."""
    content = '''```json
{
  "action": "extract",
  "reason": "页面包含岗位表格",
  "title": "2026年深圳市XX局招录公告",
  "position_type": "公务员",
  "has_establishment": true,
  "city": "深圳",
  "positions": [
    {
      "org": "深圳市XX局",
      "title": "信息技术岗",
      "count": 2,
      "education": "本科及以上",
      "major": "计算机科学与技术",
      "age_limit": "35周岁以下",
      "political_requirement": "不限",
      "registration_start": "2026-05-15",
      "registration_end": "2026-06-01"
    }
  ]
}
```'''
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    result = json.loads(content)
    assert result["action"] == "extract"
    assert len(result["positions"]) == 1


def test_json_extraction_download_action():
    """Should parse download action format."""
    content = '''```json
{
  "action": "download",
  "reason": "岗位表在附件中",
  "title": "测试公告",
  "attachments": [
    {"url": "https://example.com/pos.pdf", "type": "pdf"}
  ]
}
```'''
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    result = json.loads(content)
    assert result["action"] == "download"
    assert len(result["attachments"]) == 1
    assert result["attachments"][0]["type"] == "pdf"


def test_json_extraction_follow_action():
    """Should parse follow action format."""
    content = '{"action": "follow", "links": [{"url": "https://example.com/detail"}]}'
    result = json.loads(content)
    assert result["action"] == "follow"
    assert result["links"][0]["url"] == "https://example.com/detail"


def test_json_extraction_skip_action():
    """Should parse skip action format."""
    content = '{"action": "skip", "reason": "无关页面"}'
    result = json.loads(content)
    assert result["action"] == "skip"
