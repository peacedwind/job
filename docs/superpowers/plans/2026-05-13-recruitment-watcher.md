# Recruitment Watcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal viable system that crawls Shenzhen recruitment announcements, filters matching positions, and sends email notifications.

**Architecture:** Modular Python project with clear separation: crawler fetches HTML, parser extracts structured data, filter applies 6 hard rules, storage handles SQLite, notifier sends email. Main.py orchestrates the flow.

**Tech Stack:** Python 3.10+, Playwright (browser automation), BeautifulSoup4 + lxml (HTML parsing), SQLite (storage), smtplib (QQ SMTP email), pytest (testing)

---

## File Structure

```
recruitment-watcher/
├── main.py                     # Entry point: orchestrate full flow
├── config.py                   # All configuration constants
├── requirements.txt            # Dependencies
├── crawler/
│   ├── __init__.py
│   └── shenzhen.py             # Shenzhen exam institute crawler
├── parser/
│   ├── __init__.py
│   └── rule_parser.py          # HTML → structured position data
├── filter/
│   ├── __init__.py
│   └── matcher.py              # 6 hard filters + dedup
├── notifier/
│   ├── __init__.py
│   └── email_sender.py         # QQ SMTP email sender
├── storage/
│   ├── __init__.py
│   └── db.py                   # SQLite operations
├── tests/
│   ├── __init__.py
│   ├── test_storage.py         # Tests for db.py
│   ├── test_parser.py          # Tests for rule_parser.py
│   ├── test_filter.py          # Tests for matcher.py
│   └── test_notifier.py        # Tests for email_sender.py
```

---

### Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `config.py`
- Create: `crawler/__init__.py`
- Create: `parser/__init__.py`
- Create: `filter/__init__.py`
- Create: `notifier/__init__.py`
- Create: `storage/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create all directories**

```bash
mkdir -p crawler parser filter notifier storage tests
```

- [ ] **Step 2: Create requirements.txt**

```txt
playwright==1.49.1
beautifulsoup4==4.12.3
lxml==5.3.0
pytest==8.3.4
```

- [ ] **Step 3: Create config.py**

```python
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
```

- [ ] **Step 4: Create all __init__.py files**

```bash
touch crawler/__init__.py parser/__init__.py filter/__init__.py notifier/__init__.py storage/__init__.py tests/__init__.py
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -r requirements.txt
playwright install chromium
```

- [ ] **Step 6: Initialize git and commit**

```bash
git init
git add .
git commit -m "feat: project scaffolding with config and directory structure"
```

---

### Task 2: Storage Layer (db.py)

**Files:**
- Create: `storage/db.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write failing test for database initialization**

```python
# tests/test_storage.py
import os
import sqlite3
import pytest
from storage.db import Database


@pytest.fixture
def db(tmp_path):
    """Create a temporary database for each test."""
    db_path = str(tmp_path / "test.db")
    return Database(db_path)


def test_init_creates_tables(db):
    """Database initialization should create positions and crawl_logs tables."""
    conn = sqlite3.connect(db.db_path)
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    assert "positions" in tables
    assert "crawl_logs" in tables


def test_positions_table_schema(db):
    """Positions table should have the correct columns."""
    conn = sqlite3.connect(db.db_path)
    cursor = conn.execute("PRAGMA table_info(positions)")
    columns = {row[1] for row in cursor.fetchall()}
    conn.close()
    expected = {"id", "hash", "city", "position_type", "org", "title",
                "source_url", "source_name", "first_seen_at", "notified_at",
                "registration_end", "status"}
    assert expected == columns
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_storage.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'storage.db'`

- [ ] **Step 3: Implement Database class**

```python
# storage/db.py
import sqlite3
from datetime import datetime


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_tables()

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def _init_tables(self):
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS positions (
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
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crawl_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_name TEXT,
                crawl_time TEXT,
                status TEXT,
                new_count INTEGER DEFAULT 0,
                error_message TEXT
            )
        """)
        conn.commit()
        conn.close()

    def insert_position(self, position: dict) -> bool:
        """Insert a position. Returns True if inserted, False if duplicate."""
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO positions
                   (hash, city, position_type, org, title, source_url,
                    source_name, first_seen_at, registration_end, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    position["hash"],
                    position["city"],
                    position.get("position_type"),
                    position.get("org"),
                    position.get("title"),
                    position.get("source_url"),
                    position.get("source_name"),
                    datetime.now().isoformat(),
                    position.get("registration_end"),
                    "active",
                ),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    def hash_exists(self, hash_value: str) -> bool:
        """Check if a position hash already exists."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT 1 FROM positions WHERE hash = ?", (hash_value,)
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def log_crawl(self, source_name: str, status: str,
                   new_count: int = 0, error_message: str = None):
        """Record a crawl attempt."""
        conn = self._get_conn()
        conn.execute(
            """INSERT INTO crawl_logs
               (source_name, crawl_time, status, new_count, error_message)
               VALUES (?, ?, ?, ?, ?)""",
            (source_name, datetime.now().isoformat(), status,
             new_count, error_message),
        )
        conn.commit()
        conn.close()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_storage.py -v
```

Expected: 2 passed

- [ ] **Step 5: Write test for insert and dedup**

```python
# tests/test_storage.py (append)

def test_insert_position_returns_true_on_new(db):
    """Inserting a new position should return True."""
    pos = {
        "hash": "abc123",
        "city": "深圳",
        "position_type": "公务员",
        "org": "深圳市XX局",
        "title": "信息技术岗",
        "source_url": "https://example.com/1",
        "source_name": "深圳考试院",
        "registration_end": "2026-06-01",
    }
    assert db.insert_position(pos) is True


def test_insert_position_returns_false_on_duplicate(db):
    """Inserting a duplicate position should return False."""
    pos = {
        "hash": "abc123",
        "city": "深圳",
        "position_type": "公务员",
        "org": "深圳市XX局",
        "title": "信息技术岗",
        "source_url": "https://example.com/1",
        "source_name": "深圳考试院",
        "registration_end": "2026-06-01",
    }
    db.insert_position(pos)
    assert db.insert_position(pos) is False


def test_hash_exists(db):
    """hash_exists should return True for known hashes."""
    pos = {
        "hash": "def456",
        "city": "深圳",
        "source_url": "https://example.com/2",
        "source_name": "深圳考试院",
    }
    db.insert_position(pos)
    assert db.hash_exists("def456") is True
    assert db.hash_exists("unknown") is False
```

- [ ] **Step 6: Run all storage tests**

```bash
python -m pytest tests/test_storage.py -v
```

Expected: 5 passed

- [ ] **Step 7: Commit**

```bash
git add storage/db.py tests/test_storage.py
git commit -m "feat: SQLite storage layer with positions table and dedup"
```

---

### Task 3: Parser (rule_parser.py)

**Files:**
- Create: `parser/rule_parser.py`
- Create: `tests/test_parser.py`

- [ ] **Step 1: Write failing test for position table parsing**

```python
# tests/test_parser.py
import pytest
from parser.rule_parser import parse_detail_page, parse_position_table


SAMPLE_TABLE_HTML = """
<div class="content">
<table>
<thead>
<tr><th>招录单位</th><th>岗位名称</th><th>招录人数</th><th>学历</th><th>专业</th><th>年龄</th><th>政治面貌</th></tr>
</thead>
<tbody>
<tr><td>深圳市XX局</td><td>信息技术岗</td><td>2</td><td>本科及以上</td><td>计算机科学与技术、软件工程</td><td>35周岁以下</td><td>不限</td></tr>
<tr><td>深圳市YY局</td><td>综合管理岗</td><td>1</td><td>硕士及以上</td><td>行政管理</td><td>30周岁以下</td><td>中共党员</td></tr>
</tbody>
</table>
<p>报名时间：2026年5月15日至2026年6月1日</p>
</div>
"""

SAMPLE_ANNOUNCEMENT_HTML = """
<div class="article">
<h1>2026年深圳市XX局公务员招录公告</h1>
<p>根据公务员法和公务员录用规定...</p>
{table_content}
<p>本公告由深圳市XX局负责解释。</p>
</div>
""".format(table_content=SAMPLE_TABLE_HTML)


def test_parse_position_table_extracts_rows():
    """Should extract all position rows from a table."""
    positions = parse_position_table(SAMPLE_TABLE_HTML)
    assert len(positions) == 2


def test_parse_position_table_first_row():
    """First row should have correct field values."""
    positions = parse_position_table(SAMPLE_TABLE_HTML)
    pos = positions[0]
    assert pos["org"] == "深圳市XX局"
    assert pos["title"] == "信息技术岗"
    assert pos["count"] == 2
    assert pos["education"] == "本科及以上"
    assert pos["major"] == "计算机科学与技术、软件工程"
    assert pos["age_limit"] == "35周岁以下"
    assert pos["political_requirement"] == "不限"


def test_parse_position_table_major_variations():
    """Should handle different major field formats."""
    html = """
    <table>
    <tr><th>单位</th><th>岗位</th><th>人数</th><th>学历</th><th>专业</th><th>年龄</th><th>政治面貌</th></tr>
    <tr><td>某单位</td><td>技术岗</td><td>1</td><td>本科</td><td>计算机类</td><td>40岁以下</td><td>无</td></tr>
    </table>
    """
    positions = parse_position_table(html)
    assert positions[0]["major"] == "计算机类"
    assert positions[0]["political_requirement"] == "无"


def test_parse_detail_page_extracts_metadata():
    """Should extract title, publish_date, and positions from a full page."""
    result = parse_detail_page(SAMPLE_ANNOUNCEMENT_HTML, "https://example.com/1")
    assert result["title"] == "2026年深圳市XX局公务员招录公告"
    assert result["source_url"] == "https://example.com/1"
    assert result["city"] == "深圳"
    assert len(result["positions"]) == 2


def test_parse_detail_page_registration_dates():
    """Should extract registration start and end dates."""
    result = parse_detail_page(SAMPLE_ANNOUNCEMENT_HTML, "https://example.com/1")
    pos = result["positions"][0]
    assert pos["registration_start"] == "2026-05-15"
    assert pos["registration_end"] == "2026-06-01"


def test_parse_no_table_returns_empty():
    """Page with no table should return empty positions list."""
    html = "<div><p>No positions here</p></div>"
    result = parse_detail_page(html, "https://example.com/2")
    assert result["positions"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_parser.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'parser.rule_parser'`

- [ ] **Step 3: Implement rule_parser.py**

```python
# parser/rule_parser.py
import re
from bs4 import BeautifulSoup


def parse_position_table(html: str) -> list[dict]:
    """Extract position rows from an HTML table."""
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return []

    rows = table.find_all("tr")
    if len(rows) < 2:
        return []

    # Detect header row to map column indices
    headers = [th.get_text(strip=True) for th in rows[0].find_all(["th", "td"])]
    col_map = _build_column_map(headers)

    positions = []
    for row in rows[1:]:
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) < 3:
            continue
        pos = _extract_position(cells, col_map)
        if pos:
            positions.append(pos)

    return positions


def _build_column_map(headers: list[str]) -> dict[str, int]:
    """Map Chinese header names to column indices."""
    mapping = {}
    keywords = {
        "org": ["招录单位", "用人单位", "招聘单位", "单位"],
        "title": ["岗位名称", "职位名称", "岗位", "职位"],
        "count": ["招录人数", "招聘人数", "人数", "计划数"],
        "education": ["学历", "学历要求", "最低学历"],
        "major": ["专业", "专业要求"],
        "age_limit": ["年龄", "年龄要求"],
        "political_requirement": ["政治面貌", "政治面貌要求"],
    }
    for i, header in enumerate(headers):
        for field, kws in keywords.items():
            if any(kw in header for kw in kws):
                mapping[field] = i
                break
    return mapping


def _extract_position(cells: list[str], col_map: dict[str, int]) -> dict | None:
    """Extract a position dict from table cells."""
    def get(field):
        idx = col_map.get(field)
        if idx is not None and idx < len(cells):
            return cells[idx]
        return None

    org = get("org")
    title = get("title")
    if not org and not title:
        return None

    count_str = get("count") or "1"
    count = int(re.search(r"\d+", count_str).group()) if re.search(r"\d+", count_str) else 1

    return {
        "org": org or "",
        "title": title or "",
        "count": count,
        "education": get("education") or "",
        "major": get("major") or "",
        "age_limit": get("age_limit") or "",
        "political_requirement": get("political_requirement") or "不限",
        "registration_start": None,
        "registration_end": None,
    }


def parse_detail_page(html: str, url: str) -> dict:
    """Parse a detail page into structured announcement data."""
    soup = BeautifulSoup(html, "lxml")

    # Extract title
    title = ""
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    # Extract positions from tables
    positions = parse_position_table(html)

    # Extract registration dates from surrounding text
    full_text = soup.get_text()
    dates = _extract_registration_dates(full_text)
    for pos in positions:
        pos["registration_start"] = dates.get("start")
        pos["registration_end"] = dates.get("end")

    return {
        "title": title,
        "city": "深圳",
        "source_url": url,
        "source_name": "深圳考试院",
        "publish_date": None,
        "position_type": _detect_position_type(title),
        "has_establishment": _detect_establishment(full_text),
        "positions": positions,
    }


def _extract_registration_dates(text: str) -> dict[str, str | None]:
    """Extract registration start/end dates from text."""
    # Pattern: 报名时间：YYYY年M月D日至YYYY年M月D日
    # Also handles: YYYY-MM-DD format
    result = {"start": None, "end": None}

    # Try YYYY年M月D日至YYYY年M月D日
    match = re.search(
        r"报名[时时间].*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日.*?[至到~-].*?(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
        text,
    )
    if match:
        y1, m1, d1 = match.group(1), match.group(2).zfill(2), match.group(3).zfill(2)
        y2, m2, d2 = match.group(4), match.group(5).zfill(2), match.group(6).zfill(2)
        result["start"] = f"{y1}-{m1}-{d1}"
        result["end"] = f"{y2}-{m2}-{d2}"
        return result

    # Try YYYY-MM-DD format
    match = re.search(
        r"报名.*?(\d{4}-\d{2}-\d{2}).*?[至到~-].*?(\d{4}-\d{2}-\d{2})",
        text,
    )
    if match:
        result["start"] = match.group(1)
        result["end"] = match.group(2)

    return result


def _detect_position_type(title: str) -> str:
    """Detect position type from title."""
    if "公务员" in title:
        return "公务员"
    if "教师" in title or "教育" in title:
        return "小学教师"
    return "事业单位"


def _detect_establishment(text: str) -> bool:
    """Detect if the announcement mentions 事业编制 or 公务员编制."""
    keywords = ["事业编制", "公务员编制", "有编制", "在编", "编制内"]
    negative = ["编外", "合同制", "劳务派遣", "非编制"]
    for kw in negative:
        if kw in text:
            return False
    for kw in keywords:
        if kw in text:
            return True
    # Default to True for government announcements (conservative)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_parser.py -v
```

Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add parser/rule_parser.py tests/test_parser.py
git commit -m "feat: HTML parser with table extraction and date parsing"
```

---

### Task 4: Filter (matcher.py)

**Files:**
- Create: `filter/matcher.py`
- Create: `tests/test_filter.py`

- [ ] **Step 1: Write failing tests for all 6 filters**

```python
# tests/test_filter.py
import pytest
from datetime import date
from filter.matcher import filter_positions


@pytest.fixture
def sample_position():
    """A position that passes all filters."""
    return {
        "org": "深圳市XX局",
        "title": "信息技术岗",
        "count": 2,
        "education": "本科及以上",
        "major": "计算机科学与技术",
        "age_limit": "35周岁以下",
        "political_requirement": "不限",
        "registration_end": "2026-12-31",
        "has_establishment": True,
        "city": "深圳",
        "source_url": "https://example.com/1",
        "position_type": "公务员",
    }


def test_passes_all_filters(sample_position):
    """A valid position should pass all filters."""
    today = date(2026, 5, 13)
    birth_date = date(1992, 11, 24)
    result = filter_positions([sample_position], today, birth_date)
    assert len(result) == 1


def test_filter_no_establishment(sample_position):
    """Positions without establishment should be filtered out."""
    sample_position["has_establishment"] = False
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_wrong_city(sample_position):
    """Positions in non-target cities should be filtered out."""
    sample_position["city"] = "北京"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_education_too_high(sample_position):
    """Positions requiring education above target should be filtered out."""
    sample_position["education"] = "硕士及以上"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_unrelated_major(sample_position):
    """Positions with unrelated majors should be filtered out."""
    sample_position["major"] = "法学、行政管理"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_political_requirement(sample_position):
    """Positions requiring party membership should be filtered out."""
    sample_position["political_requirement"] = "中共党员"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_expired_registration(sample_position):
    """Positions with expired registration should be filtered out."""
    sample_position["registration_end"] = "2026-01-01"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_age_too_old(sample_position):
    """Positions with age limit too low should be filtered out."""
    sample_position["age_limit"] = "30周岁以下"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 0


def test_filter_age_birth_after_format(sample_position):
    """Should handle 'XXXX年X月X日以后出生' format."""
    sample_position["age_limit"] = "1991年1月1日以后出生"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 1


def test_filter_multiple_positions(sample_position):
    """Should filter a list of mixed positions correctly."""
    pos2 = sample_position.copy()
    pos2["title"] = "管理岗"
    pos2["major"] = "法学"
    pos2["source_url"] = "https://example.com/2"

    today = date(2026, 5, 13)
    result = filter_positions([sample_position, pos2], today, date(1992, 11, 24))
    assert len(result) == 1
    assert result[0]["title"] == "信息技术岗"


def test_education_bachelor_accepted(sample_position):
    """本科 should be accepted."""
    sample_position["education"] = "本科"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 1


def test_major_partial_match(sample_position):
    """Should match partial major keywords like '计算机'."""
    sample_position["major"] = "计算机类"
    today = date(2026, 5, 13)
    result = filter_positions([sample_position], today, date(1992, 11, 24))
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_filter.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'filter.matcher'`

- [ ] **Step 3: Implement matcher.py**

```python
# filter/matcher.py
import re
from datetime import date


MAJOR_KEYWORDS = ["计算机", "软件工程", "信息技术", "信息管理"]
EDUCATION_RANK = {
    "高中": 1, "中专": 1,
    "大专": 2, "专科": 2,
    "本科": 3,
    "硕士": 4, "研究生": 4,
    "博士": 5,
}
TARGET_EDUCATION_RANK = 3  # 本科


def filter_positions(
    positions: list[dict],
    today: date,
    birth_date: date,
    target_cities: list[str] | None = None,
) -> list[dict]:
    """Apply all hard filters and return matching positions."""
    if target_cities is None:
        target_cities = ["深圳"]

    current_age = _calculate_age(birth_date, today)

    results = []
    for pos in positions:
        if not _check_establishment(pos):
            continue
        if not _check_city(pos, target_cities):
            continue
        if not _check_education(pos):
            continue
        if not _check_major(pos):
            continue
        if not _check_political(pos):
            continue
        if not _check_age(pos, current_age, birth_date):
            continue
        if not _check_timeliness(pos, today):
            continue
        results.append(pos)

    return results


def _calculate_age(birth_date: date, today: date) -> int:
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def _check_establishment(pos: dict) -> bool:
    return pos.get("has_establishment", False) is True


def _check_city(pos: dict, target_cities: list[str]) -> bool:
    return pos.get("city", "") in target_cities


def _check_education(pos: dict) -> bool:
    """Position education requirement must be <= target (本科)."""
    edu = pos.get("education", "")
    for keyword, rank in EDUCATION_RANK.items():
        if keyword in edu:
            return rank <= TARGET_EDUCATION_RANK
    # If we can't determine, be permissive
    return True


def _check_major(pos: dict) -> bool:
    """Position major must contain at least one target keyword."""
    major = pos.get("major", "")
    if not major:
        return True  # No major requirement = any major OK
    return any(kw in major for kw in MAJOR_KEYWORDS)


def _check_political(pos: dict) -> bool:
    """Exclude positions requiring party membership."""
    req = pos.get("political_requirement", "不限")
    if not req or req in ("不限", "无", ""):
        return True
    # Reject if it requires party membership
    party_keywords = ["党员", "预备党员", "中共党员"]
    return not any(kw in req for kw in party_keywords)


def _check_age(pos: dict, current_age: int, birth_date: date) -> bool:
    """Check if age meets the position requirement."""
    age_limit = pos.get("age_limit", "")
    if not age_limit:
        return True  # No age requirement

    # Pattern: "XX周岁以下"
    match = re.search(r"(\d+)\s*周岁以下", age_limit)
    if match:
        max_age = int(match.group(1))
        return current_age <= max_age

    # Pattern: "XXXX年X月X日以后出生"
    match = re.search(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日以后出生", age_limit)
    if match:
        y, m, d = int(match.group(1)), int(match.group(2)), int(match.group(3))
        cutoff = date(y, m, d)
        return birth_date >= cutoff

    # Pattern: "XX岁以下"
    match = re.search(r"(\d+)\s*岁以下", age_limit)
    if match:
        max_age = int(match.group(1))
        return current_age <= max_age

    # Can't parse, be permissive
    return True


def _check_timeliness(pos: dict, today: date) -> bool:
    """Check registration hasn't expired."""
    end = pos.get("registration_end")
    if not end:
        return True  # No end date = assume active
    try:
        end_date = date.fromisoformat(end)
        return end_date >= today
    except ValueError:
        return True  # Can't parse = be permissive
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_filter.py -v
```

Expected: 12 passed

- [ ] **Step 5: Commit**

```bash
git add filter/matcher.py tests/test_filter.py
git commit -m "feat: 6 hard filters with age, education, major, political checks"
```

---

### Task 5: Crawler (shenzhen.py)

**Files:**
- Create: `crawler/shenzhen.py`

- [ ] **Step 1: Implement the Shenzhen crawler**

This module uses Playwright to fetch real pages. Unit testing requires live sites, so we test via the integration run in Task 7.

```python
# crawler/shenzhen.py
import asyncio
from playwright.async_api import async_playwright, Page


async def crawl_list_page(page: Page, url: str, max_pages: int = 3) -> list[dict]:
    """Crawl the Shenzhen exam institute announcement list.
    Returns list of {title, date, url} dicts.
    """
    announcements = []

    for page_num in range(max_pages):
        if page_num == 0:
            page_url = url
        else:
            # URL pattern: index.html, index_1.html, index_2.html, ...
            page_url = url.replace("index.html", f"index_{page_num}.html")

        try:
            await page.goto(page_url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1000)

            items = await _extract_list_items(page)
            if not items:
                break  # No more pages
            announcements.extend(items)
        except Exception as e:
            print(f"Error crawling list page {page_url}: {e}")
            break

    return announcements


async def _extract_list_items(page: Page) -> list[dict]:
    """Extract announcement items from the current list page."""
    items = await page.evaluate("""
        () => {
            const results = [];
            // Try multiple selectors for government CMS patterns
            const selectors = [
                '.list-box li', '.news-list li', '.xxgk-list li',
                '.right-list li', '.listContent li', 'ul.list li',
                '.zwgk-list li', 'table.list tr'
            ];
            let elements = [];
            for (const sel of selectors) {
                elements = document.querySelectorAll(sel);
                if (elements.length > 0) break;
            }
            // Fallback: try all <a> tags with date-like text nearby
            if (elements.length === 0) {
                elements = document.querySelectorAll('li, tr');
            }
            for (const el of elements) {
                const link = el.querySelector('a');
                const dateEl = el.querySelector('.date, .time, span:last-child, td:last-child');
                if (link && link.href) {
                    const title = link.getAttribute('title') || link.textContent.trim();
                    const dateText = dateEl ? dateEl.textContent.trim() : '';
                    // Filter out navigation links
                    if (title && title.length > 5 && dateText.match(/\\d{4}[-/]\\d{2}[-/]\\d{2}/)) {
                        results.push({
                            title: title,
                            date: dateText,
                            url: link.href
                        });
                    }
                }
            }
            return results;
        }
    """)
    return items


async def crawl_detail_page(page: Page, url: str) -> str | None:
    """Fetch the HTML content of a detail page."""
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await page.wait_for_timeout(500)
        html = await page.content()
        return html
    except Exception as e:
        print(f"Error crawling detail page {url}: {e}")
        return None


async def crawl_shenzhen(config: dict) -> list[dict]:
    """Main entry point for Shenzhen crawling.
    Returns list of {title, date, url, detail_html} dicts.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        # Set a reasonable user agent
        await page.set_extra_http_headers({
            "Accept-Language": "zh-CN,zh;q=0.9"
        })

        print(f"Crawling Shenzhen list: {config['list_url']}")
        announcements = await crawl_list_page(
            page, config["list_url"], max_pages=config.get("max_pages", 3)
        )
        print(f"Found {len(announcements)} announcements")

        # Fetch detail pages (limit to first 20 for MVP)
        results = []
        for i, ann in enumerate(announcements[:20]):
            print(f"  Fetching detail {i+1}/{min(len(announcements), 20)}: {ann['title'][:40]}...")
            html = await crawl_detail_page(page, ann["url"])
            if html:
                results.append({
                    "title": ann["title"],
                    "date": ann["date"],
                    "url": ann["url"],
                    "detail_html": html,
                })

        await browser.close()

    return results
```

- [ ] **Step 2: Commit**

```bash
git add crawler/shenzhen.py
git commit -m "feat: Shenzhen crawler with list and detail page fetching"
```

---

### Task 6: Notifier (email_sender.py)

**Files:**
- Create: `notifier/email_sender.py`
- Create: `tests/test_notifier.py`

- [ ] **Step 1: Write failing tests for email formatting**

```python
# tests/test_notifier.py
import pytest
from datetime import date
from notifier.email_sender import format_email_body, format_email_subject


def test_format_email_subject_with_positions():
    subject = format_email_subject(date(2026, 5, 13), 3)
    assert "2026-05-13" in subject
    assert "3" in subject
    assert "招考日报" in subject


def test_format_email_subject_zero():
    subject = format_email_subject(date(2026, 5, 13), 0)
    assert "2026-05-13" in subject


def test_format_email_body_with_positions():
    positions = [
        {
            "org": "深圳市XX局",
            "title": "信息技术岗",
            "count": 2,
            "education": "本科及以上",
            "major": "计算机科学与技术",
            "registration_start": "2026-05-15",
            "registration_end": "2026-06-01",
            "source_url": "https://example.com/1",
            "source_name": "深圳考试院",
            "position_type": "公务员",
            "has_establishment": True,
        }
    ]
    body = format_email_body(positions, date(2026, 5, 13))
    assert "深圳市XX局" in body
    assert "信息技术岗" in body
    assert "深圳考试院" in body
    assert "https://example.com/1" in body
    assert "有编制" in body


def test_format_email_body_empty():
    body = format_email_body([], date(2026, 5, 13))
    assert "无新增" in body


def test_format_email_body_multiple_cities():
    positions = [
        {
            "org": "深圳市XX局", "title": "技术岗", "count": 1,
            "education": "本科", "major": "计算机类",
            "registration_start": "2026-05-15", "registration_end": "2026-06-01",
            "source_url": "https://a.com", "source_name": "深圳考试院",
            "position_type": "公务员", "has_establishment": True,
            "city": "深圳",
        },
    ]
    body = format_email_body(positions, date(2026, 5, 13))
    assert "深圳" in body
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_notifier.py -v
```

Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement email_sender.py**

```python
# notifier/email_sender.py
import smtplib
from datetime import date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def format_email_subject(day: date, count: int) -> str:
    return f"[招考日报] {day.isoformat()} 新增 {count} 个匹配岗位"


def format_email_body(positions: list[dict], today: date) -> str:
    if not positions:
        return (
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"今日无新增匹配岗位\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    # Group by city
    city_groups: dict[str, list[dict]] = {}
    for pos in positions:
        city = pos.get("city", "其他")
        city_groups.setdefault(city, []).append(pos)

    city_icons = {"深圳": "🔴", "杭州": "🟡", "武汉": "🟢"}

    lines = ["━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", ""]
    idx = 1

    for city in ["深圳", "杭州", "武汉"]:
        icon = city_icons.get(city, "⚪")
        city_positions = city_groups.get(city, [])
        lines.append(f"{icon} {city} ({len(city_positions)}个)")
        lines.append("")

        if not city_positions:
            lines.append("   今日无新增匹配岗位")
            lines.append("")
            continue

        for pos in city_positions:
            est_text = "(有编制)" if pos.get("has_establishment") else "(无编制)"
            lines.append(f"{idx}. {pos['org']} - {pos['title']} {est_text}")
            lines.append(f"   类型：{pos.get('position_type', '未知')}")
            lines.append(
                f"   招录：{pos.get('count', 1)}人 | {pos['education']} | {pos['major']}"
            )
            lines.append(f"   报名：{pos.get('registration_start', '未知')} 至 {pos.get('registration_end', '未知')}")
            lines.append(f"   来源：{pos.get('source_name', '未知')}")
            lines.append(f"   链接：{pos['source_url']}")
            lines.append("")
            idx += 1

    # Timeline reminders (next 7 days)
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("⏰ 近期时间节点提醒 (未来7天)")
    reminders = _collect_reminders(positions, today)
    if reminders:
        for rem in reminders:
            lines.append(f"   - {rem}")
    else:
        lines.append("   无近期时间节点")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


def _collect_reminders(positions: list[dict], today: date) -> list[str]:
    """Collect registration start/end dates within next 7 days."""
    reminders = []
    cutoff = today + timedelta(days=7)

    for pos in positions:
        start = pos.get("registration_start")
        end = pos.get("registration_end")
        org = pos.get("org", "")
        title = pos.get("title", "")

        if start:
            try:
                start_date = date.fromisoformat(start)
                if today <= start_date <= cutoff:
                    reminders.append(f"{start} {org} {title} 报名开始")
            except ValueError:
                pass

        if end:
            try:
                end_date = date.fromisoformat(end)
                if today <= end_date <= cutoff:
                    reminders.append(f"{end} {org} {title} 报名截止")
            except ValueError:
                pass

    reminders.sort()
    return reminders


def send_email(config: dict, subject: str, body: str) -> bool:
    """Send email via QQ SMTP. Returns True on success."""
    try:
        msg = MIMEMultipart()
        msg["From"] = config["sender_email"]
        msg["To"] = config["receiver_email"]
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP_SSL(config["smtp_host"], config["smtp_port"]) as server:
            server.login(config["sender_email"], config["sender_password"])
            server.send_message(msg)

        print(f"Email sent to {config['receiver_email']}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_notifier.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add notifier/email_sender.py tests/test_notifier.py
git commit -m "feat: email formatter and QQ SMTP sender"
```

---

### Task 7: Hash Utility & Dedup

**Files:**
- Create: `filter/matcher.py` (add hash function)

- [ ] **Step 1: Add position hash function to matcher.py**

Append to `filter/matcher.py`:

```python
import hashlib


def compute_position_hash(position: dict) -> str:
    """Compute a unique hash for a position based on source_url + title + org."""
    key = f"{position.get('source_url', '')}{position.get('title', '')}{position.get('org', '')}"
    return hashlib.md5(key.encode()).hexdigest()
```

- [ ] **Step 2: Write test for hash function**

Append to `tests/test_filter.py`:

```python
from filter.matcher import compute_position_hash


def test_hash_deterministic():
    pos = {"source_url": "https://a.com", "title": "技术岗", "org": "XX局"}
    h1 = compute_position_hash(pos)
    h2 = compute_position_hash(pos)
    assert h1 == h2


def test_hash_different_for_different_positions():
    pos1 = {"source_url": "https://a.com", "title": "技术岗", "org": "XX局"}
    pos2 = {"source_url": "https://b.com", "title": "管理岗", "org": "YY局"}
    assert compute_position_hash(pos1) != compute_position_hash(pos2)
```

- [ ] **Step 3: Run tests**

```bash
python -m pytest tests/test_filter.py -v
```

Expected: 14 passed

- [ ] **Step 4: Commit**

```bash
git add filter/matcher.py tests/test_filter.py
git commit -m "feat: position hash for deduplication"
```

---

### Task 8: Main Entry Point (main.py)

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement main.py**

```python
# main.py
import asyncio
import hashlib
from datetime import date

import config
from crawler.shenzhen import crawl_shenzhen
from parser.rule_parser import parse_detail_page
from filter.matcher import filter_positions, compute_position_hash
from storage.db import Database
from notifier.email_sender import (
    format_email_subject,
    format_email_body,
    send_email,
)


async def run():
    print("=" * 50)
    print("公职招考信息聚合系统 启动")
    print("=" * 50)

    db = Database(config.DB_PATH)
    today = date.today()

    # Step 1: Crawl
    print("\n[1/5] 采集深圳考试院公告...")
    try:
        raw_announcements = await crawl_shenzhen({
            "list_url": config.SHENZHEN_LIST_URL,
            "max_pages": 3,
        })
        db.log_crawl("深圳考试院", "success", len(raw_announcements))
    except Exception as e:
        print(f"采集失败: {e}")
        db.log_crawl("深圳考试院", "failed", error_message=str(e))
        raw_announcements = []

    print(f"采集到 {len(raw_announcements)} 条公告")

    # Step 2: Parse
    print("\n[2/5] 解析公告内容...")
    all_positions = []
    for ann in raw_announcements:
        parsed = parse_detail_page(ann["detail_html"], ann["url"])
        for pos in parsed["positions"]:
            pos["city"] = parsed["city"]
            pos["source_url"] = parsed["source_url"]
            pos["source_name"] = parsed["source_name"]
            pos["position_type"] = parsed["position_type"]
            pos["has_establishment"] = parsed["has_establishment"]
            all_positions.append(pos)

    print(f"解析出 {len(all_positions)} 个岗位")

    # Step 3: Filter
    print("\n[3/5] 筛选匹配岗位...")
    matched = filter_positions(all_positions, today, config.BIRTH_DATE)
    print(f"匹配 {len(matched)} 个岗位")

    # Step 4: Dedup & Store
    print("\n[4/5] 去重并存储...")
    new_positions = []
    for pos in matched:
        pos["hash"] = compute_position_hash(pos)
        if not db.hash_exists(pos["hash"]):
            db.insert_position(pos)
            new_positions.append(pos)

    print(f"新增 {len(new_positions)} 个岗位")

    # Step 5: Notify
    print("\n[5/5] 发送邮件通知...")
    subject = format_email_subject(today, len(new_positions))
    body = format_email_body(new_positions, today)

    if config.SENDER_EMAIL and config.SENDER_PASSWORD and config.RECEIVER_EMAIL:
        send_email(
            {
                "smtp_host": config.SMTP_HOST,
                "smtp_port": config.SMTP_PORT,
                "sender_email": config.SENDER_EMAIL,
                "sender_password": config.SENDER_PASSWORD,
                "receiver_email": config.RECEIVER_EMAIL,
            },
            subject,
            body,
        )
    else:
        print("邮件未配置，跳过发送。以下是邮件内容：")
        print(f"\n主题: {subject}")
        print(body)

    print("\n" + "=" * 50)
    print("运行完成")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run())
```

- [ ] **Step 2: Test dry run (no email configured)**

```bash
python main.py
```

Expected: Runs through all 5 steps. Prints "邮件未配置" and shows email content. May fail on crawling if the site is down or structure changed — that's OK for now.

- [ ] **Step 3: Commit**

```bash
git add main.py
git commit -m "feat: main entry point wiring all modules together"
```

---

### Task 9: Integration Verification

- [ ] **Step 1: Run all tests**

```bash
python -m pytest tests/ -v
```

Expected: All tests pass (storage: 5, parser: 6, filter: 14, notifier: 5 = 30 total)

- [ ] **Step 2: Run the full system once**

```bash
python main.py
```

Expected: Full pipeline executes. If the site works, you'll see announcements parsed and filtered. Email will print to console since not configured.

- [ ] **Step 3: Configure email and re-run**

Edit `config.py` to fill in:
- `SENDER_EMAIL` = your QQ email
- `SENDER_PASSWORD` = QQ SMTP authorization code
- `RECEIVER_EMAIL` = target email

Then:
```bash
python main.py
```

Expected: Email sent successfully with filtered positions.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "feat: recruitment watcher MVP complete"
```
