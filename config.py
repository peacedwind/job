from datetime import date

# === 筛选条件 ===
BIRTH_DATE = date(1992, 11, 24)
EDUCATION = "本科及以上"
MAJORS = ["计算机科学与技术", "软件工程", "信息技术", "计算机类"]
CITIES = ["深圳"]
POLITICAL = "不限"

# === 邮件配置 (QQ SMTP) ===
SMTP_HOST = "smtp.qq.com"
SMTP_PORT = 465
SENDER_EMAIL = ""       # 待填: 你的QQ邮箱
SENDER_PASSWORD = ""    # 待填: QQ邮箱授权码
RECEIVER_EMAIL = ""     # 待填: 收件邮箱

# === 数据源 ===
SHENZHEN_LIST_URL = "https://hrss.sz.gov.cn/szksy/zwgk/tzgg/index.html"
SHENZHEN_DETAIL_PREFIX = "https://hrss.sz.gov.cn/szksy/zwgk/tzgg/content/"

# === 数据库 ===
DB_PATH = "recruitment.db"

# === LLM (第二阶段) ===
DEEPSEEK_API_KEY = ""
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
