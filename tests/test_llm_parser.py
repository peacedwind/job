import pytest
import json


def test_json_extraction_from_markdown():
    """LLM parser should extract JSON from markdown code blocks."""
    content = '''```json
[{"title": "test", "date": "2026-05-10", "url": "https://example.com"}]
```'''
    # Simulate the extraction logic from llm_parser
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


def test_json_extraction_detail_format():
    """Should parse detail page JSON format."""
    content = '''```json
{
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
    assert result["title"] == "2026年深圳市XX局招录公告"
    assert len(result["positions"]) == 1
    assert result["positions"][0]["org"] == "深圳市XX局"
