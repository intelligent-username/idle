"""DB tests using tmp_path only."""

import sqlite3
from pathlib import Path

from idle.db import SCHEMA_VERSION
from idle.db import get_db
from idle.db import migrate

EXPECTED_TABLES = {
    "typing_sessions",
    "key_stats",
    "bigram_stats",
    "lc_problems",
    "lc_attempts",
    "lc_progress",
}


def _table_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table';"
    ).fetchall()
    return {str(r[0]) for r in rows}


def test_schema_version_constant() -> None:
    assert SCHEMA_VERSION == 1


def test_migrate_creates_all_tables(tmp_path: Path) -> None:
    conn: sqlite3.Connection = get_db(tmp_path / "idle.db")
    try:
        assert EXPECTED_TABLES.issubset(_table_names(conn))
        row = conn.execute("PRAGMA user_version;").fetchone()
        assert int(row[0]) == 1
    finally:
        conn.close()


def test_migrate_idempotent(tmp_path: Path) -> None:
    db_file: Path = tmp_path / "idle.db"
    first: sqlite3.Connection = get_db(db_file)
    first.close()
    second: sqlite3.Connection = get_db(db_file)
    try:
        assert EXPECTED_TABLES.issubset(_table_names(second))
        row = second.execute("PRAGMA user_version;").fetchone()
        assert int(row[0]) == 1
    finally:
        second.close()


def test_migrate_raw_connection(tmp_path: Path) -> None:
    db_file: Path = tmp_path / "raw.db"
    conn: sqlite3.Connection = sqlite3.connect(str(db_file))
    try:
        migrate(conn)
        assert EXPECTED_TABLES.issubset(_table_names(conn))
    finally:
        conn.close()
