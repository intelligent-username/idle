"""SQLite setup with forward-only migrations."""

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1


def _migrate_0_to_1(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS typing_sessions(id INTEGER PRIMARY KEY, ts TEXT NOT NULL, mode TEXT NOT NULL, duration_s REAL NOT NULL, net_wpm REAL NOT NULL, raw_wpm REAL NOT NULL, accuracy REAL NOT NULL, consistency REAL NOT NULL, text_len INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS key_stats(session_id INTEGER NOT NULL REFERENCES typing_sessions(id) ON DELETE CASCADE, char TEXT NOT NULL, attempts INTEGER NOT NULL, misses INTEGER NOT NULL, total_latency_ms REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS bigram_stats(session_id INTEGER NOT NULL REFERENCES typing_sessions(id) ON DELETE CASCADE, bigram TEXT NOT NULL, count INTEGER NOT NULL, total_latency_ms REAL NOT NULL);
        CREATE TABLE IF NOT EXISTS lc_problems(id INTEGER PRIMARY KEY, slug TEXT UNIQUE NOT NULL, title TEXT NOT NULL, difficulty TEXT NOT NULL, tags_json TEXT NOT NULL, cached_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS lc_attempts(id INTEGER PRIMARY KEY, problem_id INTEGER NOT NULL, ts TEXT NOT NULL, kind TEXT NOT NULL, lang TEXT NOT NULL, verdict TEXT NOT NULL, runtime_ms INTEGER, memory_mb REAL);
        CREATE TABLE IF NOT EXISTS lc_progress(problem_id INTEGER PRIMARY KEY, status TEXT NOT NULL, started_at TEXT, solved_at TEXT);
        """
    )


MIGRATIONS = {0: _migrate_0_to_1}


def migrate(conn: sqlite3.Connection) -> None:
    """Apply forward migrations and set PRAGMA user_version."""
    row = conn.execute("PRAGMA user_version;").fetchone()
    version: int = int(row[0]) if row else 0
    if version == SCHEMA_VERSION:
        return
    if version > SCHEMA_VERSION:
        raise ValueError(f"unknown schema version {version}")
    while version < SCHEMA_VERSION:
        step = MIGRATIONS.get(version)
        if step is None:
            raise ValueError(f"missing migration for version {version}")
        step(conn)
        version += 1
        conn.execute(f"PRAGMA user_version = {version};")
    conn.commit()


def get_db(path: Path) -> sqlite3.Connection:
    """Open DB at path, ensuring dirs and running migrations."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn: sqlite3.Connection = sqlite3.connect(str(path))
    conn.execute("PRAGMA foreign_keys = ON;")
    migrate(conn)
    return conn
