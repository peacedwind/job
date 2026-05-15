from datetime import date

# === 公告时效 ===
MAX_ANNOUNCEMENT_DAYS = 7  # 只处理最近N天内发布的公告

# === 筛选条件 ===
BIRTH_DATE = date(1992, 11, 24)
EDUCATION = "博士"
MAJORS = ["计算机科学与技术", "软件工程", "信息技术", "计算机类", "文学", "医学"]
CITIES = ["深圳"]
POLITICAL = "不限"

# === 邮件配置 (QQ SMTP) ===
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = "984358499@qq.com"       # 待填: 你的QQ邮箱
SENDER_PASSWORD = "your-qq-smtp-password"    # 待填: QQ邮箱授权码
RECEIVER_EMAIL = "2035255649@qq.com"     # 待填: 收件邮箱

# === 数据源 ===
DATA_SOURCES = [
    {
        "name": "深圳考试院",
        "list_url": "https://hrss.sz.gov.cn/szksy/zwgk/tzgg/index.html",
    },
    {
        "name": "深圳人社局-公职招考",
        "list_url": "https://hrss.sz.gov.cn/gzryzk/index.html",
    },
]

# === 数据库 ===
DB_PATH = "recruitment.db"

# === LLM 配置 (DeepSeek) ===
DEEPSEEK_API_KEY = "your-deepseek-api-key"       # 待填: 你的 DeepSeek API Key
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-v4-flash"
