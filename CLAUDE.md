# 公职招考信息聚合与通知系统

## 1. 概述

一个本地运行的自动化系统，每天定时采集公务员、事业单位、小学教师的招考公告，按个人条件筛选匹配岗位，通过邮件发送每日更新提醒。

## 2. 用户画像与筛选条件

| 维度 | 条件 |
|------|------|
| 岗位类型 | 公务员、事业单位、小学教师 |
| 前提条件 | 有编制（排除编外/合同制） |
| 专业 | 计算机科学与技术 |
| 学历 | 本科及以上 |
| 地域优先级 | 深圳 → 杭州 → 武汉 |
| 年龄 | 1992年11月24日出生可报 |
| 政治面貌 | 不限（排除要求党员/预备党员的岗位） |
| 时效性 | 只保留报名未截止、招录未结束的岗位 |

## 3. 系统架构

```
定时触发 (每天 09:00)
    │
    ▼
信息采集层 (Playwright 浏览器自动化)
    │  访问三城市核心网站
    │  抓取原始页面内容
    ▼
解析层 (混合模式)
    │  结构规整 → 规则提取 (CSS 选择器)
    │  结构复杂 → LLM 解析 (Claude Haiku)
    │  PDF 岗表 → PDF 解析 + LLM
    ▼
筛选层
    │  编制 / 专业 / 学历 / 年龄 / 政治面貌 / 时效性
    │  去重 (和历史记录比对)
    ▼
通知层
    │  生成邮件 (三城市分组 + 时间节点 + 来源链接)
    │  发送邮件
    ▼
存储层
    │  SQLite 记录已发送岗位，避免重复通知
```

## 4. 数据源

### 4.1 三城市核心源

| 城市 | 网站 | 信息类型 | 优先级 |
|------|------|----------|--------|
| 深圳 | 深圳市人力资源和社会保障局 | 公务员/事业单位公告 | P0 |
| 深圳 | 深圳市考试院 | 报名通知、考试安排 | P0 |
| 杭州 | 浙江省人事考试网 | 省考/事业单位公告 | P0 |
| 杭州 | 杭州市人社局 | 杭州本地岗位 | P0 |
| 武汉 | 湖北省人事考试网 | 省考/事业单位公告 | P0 |
| 武汉 | 武汉市人社局 | 武汉本地岗位 | P0 |

### 4.2 补充源

| 网站 | 用途 | 优先级 |
|------|------|--------|
| 各市教育局 | 小学教师招聘公告 | P1 |
| 中公教育 / 华图教育 | 汇总解读、分数线、报录比 | P2 |

### 4.3 采集策略

- P0 每天全量扫描
- P1 每天扫描，聚焦教师招聘
- P2 作为补充，主要抓分数线和竞争数据

### 4.4 风险与应对

| 风险 | 应对方案 |
|------|----------|
| 政府网站验证码/登录 | Playwright stealth 模式 + cookie 持久化 |
| 岗位表为 PDF 附件 | 下载后用 pdfplumber + LLM 解析 |
| 网站结构变更 | LLM 解析兜底，规则解析失败时自动降级到 LLM |
| 反爬封 IP | 请求频率控制、随机延迟、可选代理池 |

## 5. 解析层设计

### 5.1 混合解析策略

| 场景 | 处理方式 |
|------|----------|
| 页面结构规整（表格、列表） | 规则提取（CSS 选择器 + BeautifulSoup） |
| 页面结构不规整 | LLM 解析（传入 HTML 片段，提取结构化字段） |
| PDF 岗位表 | pdfplumber 提取文本 + LLM 结构化 |

优先尝试规则解析，失败或置信度低时自动降级到 LLM。

### 5.2 提取的结构化字段

```json
{
  "title": "2026年深圳市XX局公务员招录公告",
  "city": "深圳",
  "source_url": "https://...",
  "source_name": "深圳人社局",
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
      "age_birth_after": "1991-01-01",
      "fresh_grad_required": false,
      "political_requirement": "无",
      "registration_start": "2026-05-15",
      "registration_end": "2026-06-01",
      "exam_date": "2026-07-05",
      "status": "报名中|已截止|未开始"
    }
  ]
}
```

## 6. 筛选逻辑

### 6.1 硬过滤规则

按以下顺序逐步过滤：

1. **编制过滤** — `has_establishment == true`，排除编外/合同制
2. **地域过滤** — city in ["深圳", "杭州", "武汉"]
3. **学历过滤** — 岗位要求 ≤ 本科（即本科可报的保留）
4. **专业过滤** — 专业字段包含"计算机"相关关键词（计算机科学与技术、软件工程、信息技术、计算机类等）
5. **政治面貌过滤** — `political_requirement` 为"无"或"不限"（排除"限党员""限预备党员"）
6. **年龄过滤** — 根据出生日期 1992-11-24 计算，岗位年龄上限 ≥ 当前年龄
7. **时效性过滤** — `registration_end >= 当前日期` 且 `status != "已截止"`

### 6.2 年龄计算逻辑

```python
from datetime import date

birth_date = date(1992, 11, 24)
today = date.today()

# 当前周岁
age = today.year - birth_date.year
if (today.month, today.day) < (birth_date.month, birth_date.day):
    age -= 1

# 筛选条件：岗位年龄上限 >= 当前年龄
# 注意：部分岗位按"XX年X月X日以后出生"表述，需要转换判断
```

### 6.3 去重策略

按 `source_url + position_title + org` 计算哈希值，与 SQLite 中的历史记录比对，只保留新增岗位。

## 7. 通知设计

### 7.1 邮件格式

```
主题：[招考日报] 2026-05-14 新增 X 个匹配岗位

正文：

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🔴 深圳 (2个)

1. 深圳市XX局 - 信息技术岗 (有编制)
   类型：公务员
   招录：2人 | 本科及以上 | 计算机科学与技术
   1992-11-24出生可报 | 不限政治面貌
   报名：2026-05-15 至 2026-06-01
   来源：深圳人社局
   链接：https://...

🟡 杭州 (1个)

2. 杭州市XX小学 - 信息技术教师 (有编制)
   类型：小学教师
   ...

🟢 武汉 (0个)

   今日无新增匹配岗位

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏰ 近期时间节点提醒 (未来7天)
   - 05-16 深圳XX局报名开始
   - 05-20 杭州XX考试缴费截止

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 来源汇总
   - 深圳人社局：1条 | 杭州人社局：1条 | 浙江人事考试网：1条
```

### 7.2 设计要点

- 三个城市按 🔴深圳 🟡杭州 🟢武汉 分组，按优先级排序
- 没有新岗位时仍发邮件，内容简短："今日无新增匹配岗位"
- 时间节点提醒只显示未来 7 天内的
- 每条岗位带原文链接，方便跳转确认

### 7.3 通知时间

每天 09:00 发送。通过 Windows 定时任务触发。

## 8. 存储设计

### 8.1 SQLite 表结构

```sql
-- 已采集的岗位记录（用于去重）
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    hash TEXT UNIQUE NOT NULL,           -- source_url + title + org 的哈希
    city TEXT NOT NULL,
    position_type TEXT,                  -- 公务员/事业单位/小学教师
    org TEXT,
    title TEXT,
    source_url TEXT,
    source_name TEXT,
    first_seen_at TEXT,                  -- 首次采集时间
    notified_at TEXT,                    -- 通知时间
    registration_end TEXT,               -- 报名截止日期
    status TEXT DEFAULT 'active'         -- active / expired
);

-- 采集日志
CREATE TABLE crawl_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_name TEXT,
    crawl_time TEXT,
    status TEXT,                         -- success / failed
    new_count INTEGER DEFAULT 0,
    error_message TEXT
);
```

### 8.2 数据清理

- 每周清理一次超过 30 天且已过期的记录
- 保持数据库体积可控

## 9. 技术栈

| 模块 | 技术 |
|------|------|
| 浏览器自动化 | Playwright (Python, stealth 模式) |
| HTML 解析 | BeautifulSoup4 + lxml |
| LLM 解析 | Claude API (Haiku, 用于复杂页面和 PDF) |
| PDF 解析 | pdfplumber |
| 数据存储 | SQLite (Python 内置) |
| 邮件发送 | smtplib (Python 内置) 或 Resend API |
| 定时调度 | Windows 定时任务 (Task Scheduler) |

### 9.1 Python 依赖

```
playwright
beautifulsoup4
lxml
anthropic
pdfplumber
schedule          # 备选调度方案
```

## 10. 成本估算

| 项目 | 成本 |
|------|------|
| LLM API (Haiku) | 每天约 $0.01-0.05（人民币几毛钱） |
| 服务器 | 0（本地运行） |
| 邮件 | 0（使用免费 SMTP 或 Resend 免费额度） |

## 11. 项目结构

```
recruitment-watcher/
├── main.py                 # 入口，定时调度
├── config.py               # 配置（筛选条件、邮件设置、数据源列表）
├── crawler/
│   ├── __init__.py
│   ├── base.py             # 爬虫基类
│   ├── shenzhen.py         # 深圳数据源
│   ├── hangzhou.py         # 杭州数据源
│   └── wuhan.py            # 武汉数据源
├── parser/
│   ├── __init__.py
│   ├── rule_parser.py      # 规则解析
│   ├── llm_parser.py       # LLM 解析
│   └── pdf_parser.py       # PDF 解析
├── filter/
│   ├── __init__.py
│   └── matcher.py          # 筛选与去重逻辑
├── notifier/
│   ├── __init__.py
│   └── email_sender.py     # 邮件发送
├── storage/
│   ├── __init__.py
│   └── db.py               # SQLite 操作
├── requirements.txt
└── README.md
```
