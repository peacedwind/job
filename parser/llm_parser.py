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
        return _extract_json(content)
    except Exception as e:
        print(f"LLM列表解析失败: {e}")
        return []


def analyze_detail_page(client: OpenAI, html: str, url: str,
                         model: str = "deepseek-chat") -> dict:
    """Analyze a detail page and decide what to do next.

    Returns a decision dict:
    {
      "action": "extract" | "follow" | "download" | "skip",
      "reason": "说明",
      "title": "公告标题",
      "position_type": "公务员/事业单位/小学教师",
      "has_establishment": true/false,
      "city": "深圳",
      "positions": [...],                    # action=extract
      "links": [{"url": "..."}],             # action=follow
      "attachments": [{"url": "...", "type": "pdf|xlsx"}]  # action=download
    }
    """
    prompt = """分析以下招考公告详情页HTML，判断下一步该做什么。

**可能的情况：**
1. 页面直接包含岗位表格 → action="extract"，提取岗位信息
2. 页面说"详见附件"或有PDF/Excel下载链接 → action="download"，返回附件URL
3. 页面有链接指向其他页面获取岗位信息 → action="follow"，返回链接
4. 页面与招考无关，或只是通知/安排 → action="skip"

**返回JSON格式：**

情况1 - 直接有岗位表：
{
  "action": "extract",
  "reason": "页面包含岗位表格",
  "title": "公告标题",
  "position_type": "公务员|事业单位|小学教师",
  "has_establishment": true,
  "city": "深圳",
  "positions": [
    {
      "org": "招录单位",
      "title": "岗位名称",
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

情况2 - 有附件需要下载：
{
  "action": "download",
  "reason": "岗位表在PDF/Excel附件中",
  "title": "公告标题",
  "position_type": "事业单位",
  "has_establishment": true,
  "city": "深圳",
  "attachments": [
    {"url": "https://...xxx.pdf", "type": "pdf"},
    {"url": "https://...xxx.xlsx", "type": "xlsx"}
  ]
}

情况3 - 需要跳转到其他页面：
{
  "action": "follow",
  "reason": "岗位信息在链接页面中",
  "title": "公告标题",
  "links": [
    {"url": "https://..."}
  ]
}

情况4 - 无关页面：
{
  "action": "skip",
  "reason": "页面不含岗位信息"
}

注意：
- has_establishment: 编外/合同制/劳务派遣=false，其他默认true
- position_type: 看标题判断，公务员/事业单位/小学教师
- city: 从内容推断，默认深圳
- 只返回JSON，不要其他文字"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是招考公告分析助手。分析页面内容，返回JSON决策。只返回JSON，不要其他文字。"},
                {"role": "user", "content": f"{prompt}\n\n页面URL: {url}\n\nHTML内容:\n{html[:25000]}"},
            ],
            temperature=0,
            max_tokens=6000,
        )
        content = response.choices[0].message.content.strip()
        result = _extract_json(content)
        # Ensure required fields
        result.setdefault("action", "skip")
        result.setdefault("title", "")
        result.setdefault("city", "深圳")
        result.setdefault("position_type", "事业单位")
        result.setdefault("has_establishment", True)
        result.setdefault("positions", [])
        result.setdefault("links", [])
        result.setdefault("attachments", [])
        result["source_url"] = url
        result["source_name"] = "深圳考试院"
        return result
    except Exception as e:
        print(f"LLM详情分析失败: {e}")
        return {
            "action": "skip",
            "reason": f"解析异常: {e}",
            "title": "",
            "city": "深圳",
            "position_type": "事业单位",
            "has_establishment": True,
            "source_url": url,
            "source_name": "深圳考试院",
            "positions": [],
            "links": [],
            "attachments": [],
        }


def parse_attachment_text(client: OpenAI, text: str, source_url: str,
                           model: str = "deepseek-chat") -> dict:
    """Parse text extracted from PDF/Excel attachment.
    Returns structured position data.
    """
    prompt = """从以下文本中提取招考岗位信息。这些文本是从PDF或Excel附件中提取的。

提取每个岗位的：
- org: 招录单位
- title: 岗位名称
- count: 招录人数（整数）
- education: 学历要求
- major: 专业要求
- age_limit: 年龄要求
- political_requirement: 政治面貌要求
- registration_start: 报名开始日期 (YYYY-MM-DD，如有)
- registration_end: 报名截止日期 (YYYY-MM-DD，如有)

返回JSON：
{
  "positions": [
    {
      "org": "...",
      "title": "...",
      "count": 1,
      "education": "本科及以上",
      "major": "计算机科学与技术",
      "age_limit": "35周岁以下",
      "political_requirement": "不限",
      "registration_start": null,
      "registration_end": null
    }
  ]
}

如果没有找到岗位信息，返回 {"positions": []}
只返回JSON，不要其他文字。"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "你是数据提取助手。只返回JSON，不要其他文字。"},
                {"role": "user", "content": f"{prompt}\n\n文本内容:\n{text[:20000]}"},
            ],
            temperature=0,
            max_tokens=6000,
        )
        content = response.choices[0].message.content.strip()
        return _extract_json(content)
    except Exception as e:
        print(f"LLM附件解析失败: {e}")
        return {"positions": []}


def _extract_json(content: str) -> dict | list:
    """Extract JSON from LLM response, handling markdown code blocks."""
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
        content = content.strip()
    return json.loads(content)
