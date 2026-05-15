import json
from openai import OpenAI


def create_client(api_key: str, base_url: str) -> OpenAI:
    return OpenAI(api_key=api_key, base_url=base_url)


def parse_list_page(client: OpenAI, html: str, model: str = "deepseek-chat") -> list[dict]:
    """Use LLM to extract announcement links from a list page.
    Returns list of {title, date, url} dicts.
    """
    prompt = """从以下HTML页面中提取招考公告列表。

请提取每条公告的：
- title: 公告标题
- date: 发布日期 (YYYY-MM-DD格式)
- url: 详情链接 (完整URL)

只返回JSON数组，不要其他文字。示例：
[
  {"title": "xxx招录公告", "date": "2026-05-10", "url": "https://..."},
  ...
]

如果页面中没有公告列表，返回空数组 []"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是数据提取助手。只返回JSON，不要其他文字。"},
                {"role": "user", "content": f"{prompt}\n\nHTML内容:\n{html[:15000]}"},
            ],
            temperature=0,
            max_tokens=4000,
        )
        content = response.choices[0].message.content.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        return json.loads(content)
    except Exception as e:
        print(f"LLM列表解析失败: {e}")
        return []


def parse_detail_page(client: OpenAI, html: str, url: str,
                       model: str = "deepseek-chat") -> dict:
    """Use LLM to extract position information from a detail page.
    Returns structured announcement data with positions.
    """
    prompt = f"""从以下招考公告详情页HTML中提取结构化信息。

请提取：
1. title: 公告标题
2. position_type: 岗位类型（公务员/事业单位/小学教师）
3. has_establishment: 是否有编制（true/false，编外/合同制/劳务派遣为false）
4. positions: 岗位列表，每个岗位包含：
   - org: 招录单位
   - title: 岗位名称
   - count: 招录人数（整数）
   - education: 学历要求
   - major: 专业要求
   - age_limit: 年龄要求
   - political_requirement: 政治面貌要求（无/不限/中共党员等）
   - registration_start: 报名开始日期 (YYYY-MM-DD)
   - registration_end: 报名截止日期 (YYYY-MM-DD)

5. city: 城市（从公告内容推断，默认深圳）

只返回JSON，不要其他文字。示例：
{{
  "title": "2026年深圳市XX局招录公告",
  "position_type": "公务员",
  "has_establishment": true,
  "city": "深圳",
  "positions": [
    {{
      "org": "深圳市XX局",
      "title": "信息技术岗",
      "count": 2,
      "education": "本科及以上",
      "major": "计算机科学与技术",
      "age_limit": "35周岁以下",
      "political_requirement": "不限",
      "registration_start": "2026-05-15",
      "registration_end": "2026-06-01"
    }}
  ]
}}

如果页面没有岗位信息，positions返回空数组。"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是数据提取助手。只返回JSON，不要其他文字。"},
                {"role": "user", "content": f"{prompt}\n\nHTML内容:\n{html[:20000]}"},
            ],
            temperature=0,
            max_tokens=6000,
        )
        content = response.choices[0].message.content.strip()
        if "```" in content:
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()
        result = json.loads(content)
        result["source_url"] = url
        result["source_name"] = "深圳考试院"
        return result
    except Exception as e:
        print(f"LLM详情解析失败: {e}")
        return {
            "title": "",
            "position_type": "事业单位",
            "has_establishment": True,
            "city": "深圳",
            "source_url": url,
            "source_name": "深圳考试院",
            "positions": [],
        }
