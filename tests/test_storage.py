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
