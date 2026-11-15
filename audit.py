import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "querify_audit.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL,
    username TEXT,
    question TEXT,
    sql_query TEXT,
    row_count INTEGER,
    status TEXT
)
"""


def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute(_SCHEMA)
    return conn


def log_query(username, question, sql_query, row_count, status):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO audit_log (ts, username, question, sql_query, row_count, status) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (time.time(), username, question, sql_query, row_count, status),
    )
    conn.commit()
    conn.close()


def get_recent_logs(limit: int = 50):
    conn = _get_conn()
    rows = conn.execute(
        "SELECT ts, username, question, sql_query, row_count, status "
        "FROM audit_log ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return rows
