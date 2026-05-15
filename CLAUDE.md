# 公职招考信息聚合与通知系统

## 概述

本地自动化系统，每天采集招考公告，按个人条件筛选匹配岗位，邮件发送每日更新。

## 筛选条件

配置项在 `config.py`，filter 自动同步读取：

| 维度 | 说明 |
|------|------|
| 学历 | config.EDUCATION，支持模糊匹配（学士=本科，研究生=硕士） |
| 专业 | config.MAJORS，关键词包含匹配（计算机/软件工程/信息技术/文学等） |
| 城市 | config.CITIES，从岗位单位名称、标题中匹配 |
| 编制 | 排除编外/合同制/劳务派遣 |
| 政治面貌 | 排除要求党员的岗位 |
| 年龄 | 根据出生日期计算，支持"XX周岁以下"和"XXXX年X月X日以后出生" |
| 时效性 | 排除报名已截止的岗位 |
| 公告时效 | config.MAX_ANNOUNCEMENT_DAYS，只处理最近N天发布的公告 |

## 架构

```
Playwright 采集列表页 → LLM 解析公告列表
    → 详情页 LLM 判断: extract / follow / download / skip
        → 直接提取 / 跟踪链接 / 下载附件(PDF/Excel)
    → 筛选(编制/专业/学历/年龄/城市/政治面貌/时效)
    → 去重(MD5哈希: source_url + title + org)
    → 邮件通知(QQ SMTP)
```

## 技术栈

| 模块 | 技术 |
|------|------|
| 浏览器自动化 | Playwright |
| LLM 解析 | DeepSeek API (OpenAI 兼容) |
| PDF 解析 | pdfplumber |
| Excel 解析 | openpyxl(.xlsx) + xlrd(.xls) |
| 数据存储 | SQLite |
| 邮件 | QQ SMTP (smtplib) |

## 项目结构

```
├── main.py              # 入口，3层采集流程
├── config.py            # 所有配置（筛选条件、数据源、邮件、LLM）
├── parser/
│   ├── llm_parser.py    # LLM 解析（列表页/详情页/附件）
│   └── attachment_parser.py  # 附件下载与解析(PDF/Excel)
├── filter/
│   └── matcher.py       # 筛选与去重
├── notifier/
│   └── email_sender.py  # 邮件发送
├── storage/
│   └── db.py            # SQLite 存储
└── tests/               # 测试
```

## 关键设计

- **全 LLM 解析**：政府网站结构不统一，统一用 LLM 提取结构化数据
- **3 层决策**：列表页→详情页→附件/链接，LLM 自动判断下一步动作
- **智能附件过滤**：根据文件名和上下文关键词判断是否下载（岗位表/招聘计划 → 下载，承诺书/须知 → 跳过）
- **curl 兜底下载**：政府站 SSL 兼容性差，优先用 curl 下载附件
