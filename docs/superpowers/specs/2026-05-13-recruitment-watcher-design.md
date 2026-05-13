# 公职招考信息聚合与通知系统 - 设计文档

## 概述

一个本地运行的自动化系统，采集公务员、事业单位、小学教师的招考公告，按个人条件筛选匹配岗位，通过邮件发送每日更新提醒。

## 分阶段计划

### 第一阶段（本次构建）— 最小可用闭环

- 深圳考试院通知公告页采集（规则解析CSS选择器）
- 结构化字段提取（标题、日期、链接）
- 进入详情页抓取公告正文，提取岗位信息
- 6项硬过滤（编制/地域/学历/专业/政治面貌/时效性）
- SQLite去重存储
- QQ邮箱SMTP发送通知邮件
- 单次运行模式（`python main.py`），定时任务后续配置

### 第二阶段（后续扩展）

- DeepSeek LLM解析兜底（复杂页面/解析失败时降级）
- PDF岗位表解析（pdfplumber + LLM）
- 杭州、武汉数据源
- Playwright stealth模式（反爬）
- Windows定时任务配置
- 历史数据清理

## 用户画像与筛选条件

| 维度 | 条件 |
|------|------|
| 岗位类型 | 公务员、事业单位、小学教师 |
| 前提条件 | 有编制（排除编外/合同制） |
| 专业 | 计算机科学与技术 |
| 学历 | 本科及以上 |
| 地域 | 第一阶段仅深圳 |
| 年龄 | 1992年11月24日出生可报 |
| 政治面貌 | 不限（排除要求党员/预备党员的岗位） |
| 时效性 | 只保留报名未截止、招录未结束的岗位 |

## 项目结构

```
recruitment-watcher/
├── main.py                 # 入口：运行完整流程
├── config.py               # 所有配置（筛选条件、邮件、数据源URL）
├── requirements.txt        # 依赖清单
├── crawler/
│   ├── __init__.py
│   └── shenzhen.py         # 深圳考试院爬虫：抓列表页 + 详情页
├── parser/
│   ├── __init__.py
│   └── rule_parser.py      # 规则解析：CSS选择器提取结构化字段
├── filter/
│   ├── __init__.py
│   └── matcher.py          # 6项硬过滤 + 去重
├── notifier/
│   ├── __init__.py
│   └── email_sender.py     # QQ邮箱SMTP发送
├── storage/
│   ├── __init__.py
│   └── db.py               # SQLite建表、查询、插入
```

### 模块职责

| 模块 | 职责 | 不负责 |
|------|------|--------|
| `crawler` | 拿到原始HTML | 不做解析 |
| `parser` | HTML → 结构化数据 | 不做筛选 |
| `filter` | 数据 → 符合条件的岗位 | 不做存储 |
| `notifier` | 格式化 + 发送邮件 | — |
| `storage` | 读写SQLite | — |
| `main.py` | 串联所有模块 | — |

## 数据流

```
main.py 启动
    │
    ├─ 1. crawler/shenzhen.py
    │     抓取列表页: hrss.sz.gov.cn/szksy/zwgk/tzgg/index.html
    │     提取每条公告的: 标题、日期、详情链接
    │     逐条进入详情页，抓取公告正文HTML
    │     返回: List[dict] (title, date, url, detail_html)
    │
    ├─ 2. parser/rule_parser.py
    │     输入: 详情页HTML
    │     解析: 岗位表(表格) → 结构化岗位列表
    │     提取: org, title, count, education, major, age_limit,
    │           political_requirement, registration_start/end
    │     判断: has_establishment (是否编制)
    │     返回: List[Position]
    │
    ├─ 3. filter/matcher.py
    │     输入: List[Position]
    │     按6项规则逐步过滤
    │     按hash去重(和SQLite比对)
    │     返回: List[Position] (仅新增匹配岗位)
    │
    ├─ 4. storage/db.py
    │     插入新岗位记录
    │     记录采集日志
    │
    └─ 5. notifier/email_sender.py
          格式化邮件(按城市分组、时间节点提醒)
          通过QQ SMTP发送
```

## 数据源

### 深圳核心源（第一阶段）

| 网站 | URL | 用途 |
|------|-----|------|
| 深圳考试院-通知公告列表 | https://hrss.sz.gov.cn/szksy/zwgk/tzgg/index.html | 招考公告列表 |
| 深圳考试院-详情页 | https://hrss.sz.gov.cn/szksy/zwgk/tzgg/content/post_*.html | 公告详情 |
| 深圳考试院-分页 | https://hrss.sz.gov.cn/szksy/zwgk/tzgg/index_{n}.html | 第2页起 |

### 列表页结构

页面为CMS列表，每页10条记录，共约13页。每条记录包含：
- 序号
- 标题（`<a title="完整标题">`，可见文本可能截断）
- 详情链接（指向主站或外部系统）
- 发布日期（YYYY-MM-DD格式）

### 采集策略

- 扫描列表页所有分页
- 逐条进入详情页抓取正文
- 详情页中可能包含岗位表格或PDF附件链接

## 解析层设计

### 第一阶段：纯规则解析

使用 BeautifulSoup + CSS 选择器提取结构化字段。

提取的字段：

```json
{
  "title": "2026年深圳市XX局公务员招录公告",
  "city": "深圳",
  "source_url": "https://...",
  "source_name": "深圳考试院",
  "publish_date": "2026-05-10",
  "position_type": "公务员|事业单位|小学教师",
  "has_establishment": true,
  "positions": [
    {
      "org": "深圳市XX局",
      "title": "信息技术岗",
      "count": 2,
      "education": "本科及以上",
      "major": "计算机科学与技术、软件工程",
      "age_limit": "35周岁以下",
      "political_requirement": "无",
      "registration_start": "2026-05-15",
      "registration_end": "2026-06-01",
      "status": "报名中"
    }
  ]
}
```

### 第二阶段：LLM兜底

- DeepSeek API（OpenAI兼容格式）
- 规则解析失败或置信度低时自动降级
- PDF岗位表：pdfplumber提取文本 + DeepSeek结构化

## 筛选逻辑

### 硬过滤规则（按顺序执行）

1. **编制过滤** — `has_establishment == true`
2. **地域过滤** — city in ["深圳"]（第一阶段）
3. **学历过滤** — 岗位要求 ≤ 本科
4. **专业过滤** — 包含"计算机"相关关键词
5. **政治面貌过滤** — 排除要求党员/预备党员
6. **时效性过滤** — registration_end >= 当前日期

### 年龄计算

```python
birth_date = date(1992, 11, 24)
age = today.year - birth_date.year
if (today.month, today.day) < (birth_date.month, birth_date.day):
    age -= 1
# 岗位年龄上限 >= 当前年龄
```

### 去重策略

按 `source_url + position_title + org` 计算哈希值，与SQLite历史记录比对。

## 存储设计

### SQLite 表结构

```sql
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,
    city TEXT NOT NULL,
    position_type TEXT,
    org TEXT,
    title TEXT,
    source_url TEXT,
    source_name TEXT,
    first_seen_at TEXT,
    notified_at TEXT,
    registration_end TEXT,
    status TEXT DEFAULT 'active'
);

CREATE TABLE crawl_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT,
    crawl_time TEXT,
    status TEXT,
    new_count INTEGER DEFAULT 0,
    error_message TEXT
);
```

## 通知设计

### 邮件格式

```
主题：[招考日报] 2026-05-14 新增 X 个匹配岗位

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔴 深圳 (2个)

1. 深圳市XX局 - 信息技术岗 (有编制)
   类型：公务员
   招录：2人 | 本科及以上 | 计算机科学与技术
   报名：2026-05-15 至 2026-06-01
   来源：深圳考试院
   链接：https://...

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⏰ 近期时间节点提醒 (未来7天)
   - 05-16 深圳XX局报名开始
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

- 无匹配岗位时仍发邮件："今日无新增匹配岗位"
- 时间节点提醒只显示未来7天内的
- 每条岗位带原文链接

### 邮件配置

- SMTP: smtp.qq.com:465 (SSL)
- 发件邮箱: 待配置
- QQ授权码: 待配置
- 收件邮箱: 待配置

## 技术栈

| 模块 | 技术 |
|------|------|
| 浏览器自动化 | Playwright (Python) |
| HTML解析 | BeautifulSoup4 + lxml |
| LLM解析（第二阶段） | DeepSeek API (OpenAI兼容) |
| PDF解析（第二阶段） | pdfplumber |
| 数据存储 | SQLite |
| 邮件发送 | smtplib (QQ SMTP) |

### 依赖清单

```
playwright
beautifulsoup4
lxml
pdfplumber
```

## 配置项

```python
from datetime import date

# 筛选条件
BIRTH_DATE = date(1992, 11, 24)
EDUCATION = "本科及以上"
MAJORS = ["计算机科学与技术", "软件工程", "信息技术", "计算机类"]
CITIES = ["深圳"]
POLITICAL = "不限"

# 邮件
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = ""
SENDER_PASSWORD = ""
RECEIVER_EMAIL = ""

# 数据源
SHENZHEN_LIST_URL = "https://hrss.sz.gov.cn/szksy/zwgk/tzgg/index.html"
SHENZHEN_DETAIL_PREFIX = "https://hrss.sz.gov.cn/szksy/zwgk/tzgg/content/"

# LLM（第二阶段）
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
```

## 错误处理

- 某个数据源抓取失败 → 记录到crawl_logs表，继续执行
- 页面解析失败 → 记录日志，跳过该条公告
- 邮件发送失败 → 打印错误到控制台
- 不做重试（第一阶段保持简单）

## 运行方式

```bash
pip install -r requirements.txt
playwright install chromium   # 首次需要安装浏览器
python main.py                # 单次运行
```

## 第二阶段扩展点

- 加入 `crawler/hangzhou.py`、`crawler/wuhan.py` 扩展城市
- 加入 `parser/llm_parser.py` 实现LLM兜底
- 加入 `parser/pdf_parser.py` 解析PDF岗位表
- 配置Windows定时任务每天09:00运行
- Playwright stealth模式防反爬
- 数据清理：每周清理超过30天的过期记录
