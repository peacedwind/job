import sqlite3
from datetime import datetime

_EDUCATION_RANK = {
    "高中": 1, "中专": 1,
    "大专": 2, "专科": 2,
    "本科": 3, "学士": 3, "大学": 3,
    "硕士研究生": 4, "硕士": 4, "研究生": 4,
    "博士研究生": 5, "博士": 5,
}


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
                url_hash TEXT,
                city TEXT NOT NULL,
                position_type TEXT,
                has_establishment BOOLEAN DEFAULT 1,
                org TEXT,
                title TEXT,
                education TEXT,
                education_level INTEGER,
                major TEXT,
                age_limit TEXT,
                political_requirement TEXT,
                count INTEGER,
                registration_start TEXT,
                registration_end TEXT,
                source_url TEXT,
                source_name TEXT,
                first_seen_at TEXT,
                notified_at TEXT,
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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_announcements (
                url_hash TEXT PRIMARY KEY,
                source_name TEXT,
                title TEXT,
                seen_at TEXT,
                has_positions BOOLEAN
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_state (
                source_name TEXT PRIMARY KEY,
                last_crawl_time TEXT,
                last_success_time TEXT
            )
        """)
        conn.commit()
        conn.close()
        self._migrate()

    def _migrate(self):
        """Add new columns to existing databases."""
        conn = self._get_conn()
        cursor = conn.execute("PRAGMA table_info(positions)")
        existing = {row[1] for row in cursor.fetchall()}
        migrations = [
            ("url_hash", "TEXT"),
            ("has_establishment", "BOOLEAN DEFAULT 1"),
            ("education", "TEXT"),
            ("education_level", "INTEGER"),
            ("major", "TEXT"),
            ("age_limit", "TEXT"),
            ("political_requirement", "TEXT"),
            ("count", "INTEGER"),
            ("registration_start", "TEXT"),
        ]
        for col, typ in migrations:
            if col not in existing:
                conn.execute(f"ALTER TABLE positions ADD COLUMN {col} {typ}")
        conn.commit()
        conn.close()

    def insert_position(self, position: dict) -> bool:
        """Insert a position. Returns True if inserted, False if duplicate."""
        # Auto-compute education_level if not set
        if position.get("education_level") is None and position.get("education"):
            position["education_level"] = self._edu_to_level(position["education"])

        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT INTO positions
                   (hash, url_hash, city, position_type, has_establishment,
                    org, title, education, education_level, major, age_limit,
                    political_requirement, count, registration_start,
                    registration_end, source_url, source_name,
                    first_seen_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    position["hash"],
                    position.get("url_hash"),
                    position["city"],
                    position.get("position_type"),
                    position.get("has_establishment", True),
                    position.get("org"),
                    position.get("title"),
                    position.get("education"),
                    position.get("education_level"),
                    position.get("major"),
                    position.get("age_limit"),
                    position.get("political_requirement"),
                    position.get("count"),
                    position.get("registration_start"),
                    position.get("registration_end"),
                    position.get("source_url"),
                    position.get("source_name"),
                    datetime.now().isoformat(),
                    "active",
                ),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()

    @staticmethod
    def _edu_to_level(education: str) -> int | None:
        """Convert education text to numeric level. Returns None if unknown."""
        for keyword, rank in _EDUCATION_RANK.items():
            if keyword in education:
                return rank
        return None

    def hash_exists(self, hash_value: str) -> bool:
        """Check if a position hash already exists."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT 1 FROM positions WHERE hash = ?", (hash_value,)
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def announcement_seen(self, url_hash: str) -> bool:
        """Check if an announcement URL has been processed before."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT 1 FROM seen_announcements WHERE url_hash = ?", (url_hash,)
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def mark_announcement_seen(self, url_hash: str, source_name: str,
                                title: str, has_positions: bool):
        """Record that an announcement has been processed."""
        conn = self._get_conn()
        conn.execute(
            """INSERT OR IGNORE INTO seen_announcements
               (url_hash, source_name, title, seen_at, has_positions)
               VALUES (?, ?, ?, ?, ?)""",
            (url_hash, source_name, title, datetime.now().isoformat(), has_positions),
        )
        conn.commit()
        conn.close()

    def get_unnotified_positions(self) -> list[dict]:
        """Get all positions that haven't been notified yet."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            "SELECT * FROM positions WHERE notified_at IS NULL"
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def mark_notified(self, position_ids: list[int]):
        """Mark positions as notified."""
        if not position_ids:
            return
        conn = self._get_conn()
        now = datetime.now().isoformat()
        conn.executemany(
            "UPDATE positions SET notified_at = ? WHERE id = ?",
            [(now, pid) for pid in position_ids],
        )
        conn.commit()
        conn.close()

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

    def update_source_state(self, source_name: str, success: bool = True):
        """Update last crawl time for a source."""
        conn = self._get_conn()
        now = datetime.now().isoformat()
        conn.execute(
            """INSERT INTO source_state (source_name, last_crawl_time, last_success_time)
               VALUES (?, ?, ?)
               ON CONFLICT(source_name) DO UPDATE SET
                 last_crawl_time = excluded.last_crawl_time,
                 last_success_time = CASE WHEN ? THEN excluded.last_success_time
                                     ELSE source_state.last_success_time END""",
            (source_name, now, now if success else None, success),
        )
        conn.commit()
        conn.close()
