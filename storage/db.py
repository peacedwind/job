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
