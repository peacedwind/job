# 公职招考信息聚合与通知系统

本地自动化系统，每天采集政府招考公告，按个人条件筛选匹配岗位，通过邮件发送每日更新。

## 功能特性

- 自动采集多个政府网站的招考公告
- LLM 智能解析公告内容，提取结构化岗位信息
- 三层决策：列表页 → 详情页 → 附件/链接，自动判断下一步动作
- 支持 PDF、Excel (.xlsx/.xls) 附件解析
- 按学历、专业、城市、年龄、政治面貌等多维度筛选
- 增量采集，避免重复处理
- 邮件通知匹配岗位

## 项目结构

```
├── main.py                 # 入口，三层采集流程
├── config.py               # 所有配置（筛选条件、数据源、邮件、LLM）
├── parser/
│   ├── llm_parser.py       # LLM 解析（列表页/详情页/附件）
│   └── attachment_parser.py # 附件下载与解析(PDF/Excel)
├── filter/
│   └── matcher.py          # 筛选与去重
├── notifier/
│   └── email_sender.py     # 邮件发送
├── storage/
│   └── db.py               # SQLite 存储
└── recruitment.db           # 数据库
```

## 配置说明

所有配置项在 `config.py` 中：

### 筛选条件

| 配置项 | 说明 | 示例 |
|--------|------|------|
| `BIRTH_DATE` | 出生日期，用于年龄筛选 | `date(1992, 11, 24)` |
| `EDUCATION` | 学历要求，支持模糊匹配（学士=本科，研究生=硕士） | `"博士"` |
| `MAJORS` | 专业关键词列表，包含匹配 | `["计算机科学与技术", "软件工程"]` |
| `CITIES` | 目标城市，从单位名称和标题中匹配 | `["深圳"]` |
| `POLITICAL` | 政治面貌要求 | `"不限"` |
| `MAX_ANNOUNCEMENT_DAYS` | 只处理最近 N 天发布的公告 | `7` |

### 邮件配置

| 配置项 | 说明 |
|--------|------|
| `SMTP_HOST` | SMTP 服务器地址 |
| `SMTP_PORT` | SMTP 端口 |
| `SENDER_EMAIL` | 发件人邮箱 |
| `SENDER_PASSWORD` | 邮箱授权码（QQ邮箱需开启 SMTP 并获取授权码） |
| `RECEIVER_EMAIL` | 收件人邮箱 |

### 数据源

`DATA_SOURCES` 列表配置采集源，每个数据源包含：
- `name`: 数据源名称
- `list_url`: 列表页 URL

### LLM 配置

| 配置项 | 说明 |
|--------|------|
| `DEEPSEEK_API_KEY` | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | API 地址 |
| `DEEPSEEK_MODEL` | 模型名称 |

## 安装与启动

### 1. 安装依赖

```bash
pip install playwright pdfplumber openpyxl xlrd httpx
playwright install chromium
```

### 2. 配置

编辑 `config.py`，填入以下必要配置：

```python
# 邮箱配置
SENDER_EMAIL = "your-email@qq.com"
SENDER_PASSWORD = "your-qq-smtp-password"  # QQ邮箱授权码
RECEIVER_EMAIL = "receiver@example.com"

# LLM 配置
DEEPSEEK_API_KEY = "your-deepseek-api-key"
```

### 3. 运行

```bash
python main.py
```

运行后系统会：
1. 采集配置的数据源列表页
2. LLM 解析公告列表，过滤时效性
3. 逐个公告进入详情页，提取岗位信息或下载附件
4. 按筛选条件匹配岗位
5. 发送邮件通知

## 筛选逻辑

系统自动排除以下岗位：
- 编外/合同制/劳务派遣岗位
- 要求党员的岗位
- 报名已截止的岗位
- 学历不匹配的岗位
- 专业不匹配的岗位
- 年龄超出要求的岗位
- 非目标城市的岗位

## 技术栈

| 模块 | 技术 |
|------|------|
| 浏览器自动化 | Playwright |
| LLM 解析 | DeepSeek API (OpenAI 兼容) |
| PDF 解析 | pdfplumber |
| Excel 解析 | openpyxl (.xlsx) + xlrd (.xls) |
| 数据存储 | SQLite |
| 邮件 | QQ SMTP (smtplib) |
