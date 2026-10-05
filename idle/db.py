"""SQLite setup with forward-only migrations."""

import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA_VERSION: int = 1
HEADER_TTL_S: float = 5.0
_HEADER_CACHE: dict[str, tuple[float, str]] = {}


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


class Connection(sqlite3.Connection):
    """Custom SQLite connection supporting dynamic patching and hooks."""
    pass


def get_db(path: Path) -> sqlite3.Connection:
    """Open DB at path, ensuring dirs and running migrations."""
    path.parent.mkdir(parents=True, exist_ok=True)
    conn: sqlite3.Connection = sqlite3.connect(str(path), factory=Connection)
    conn.execute("PRAGMA foreign_keys = ON;")
    migrate(conn)
    return conn


def _now_iso() -> str:
    """Return current UTC time as ISO8601 string."""
    return datetime.now(timezone.utc).isoformat()


def save_typing_session(
    conn: sqlite3.Connection,
    *,
    mode: str,
    duration_s: float,
    net_wpm: float,
    raw_wpm: float,
    accuracy: float,
    consistency: float,
    text_len: int,
    per_key: dict[str, dict[str, float]],
    per_bigram: dict[str, dict[str, float]],
) -> int:
    """Persist one typing session with stats in single transaction."""
    ts: str = _now_iso()
    with conn:
        cur = conn.execute(
            "INSERT INTO typing_sessions"
            "(ts, mode, duration_s, net_wpm, raw_wpm, accuracy, consistency, text_len)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            (ts, mode, duration_s, net_wpm, raw_wpm, accuracy, consistency, text_len),
        )
        if cur.lastrowid is None:
            raise RuntimeError("typing session insert failed")
        session_id: int = int(cur.lastrowid)
        key_rows = [
            (session_id, str(ch), int(v.get("attempts", 0)), int(v.get("misses", 0)), float(v.get("total_latency_ms", 0.0)))
            for ch, v in per_key.items()
        ]
        if key_rows:
            conn.executemany(
                "INSERT INTO key_stats(session_id, char, attempts, misses, total_latency_ms) VALUES (?, ?, ?, ?, ?);",
                key_rows,
            )
        bigram_rows = [
            (session_id, str(bg), int(v.get("count", 0)), float(v.get("total_latency_ms", 0.0)))
            for bg, v in per_bigram.items()
        ]
        if bigram_rows:
            conn.executemany(
                "INSERT INTO bigram_stats(session_id, bigram, count, total_latency_ms) VALUES (?, ?, ?, ?);",
                bigram_rows,
            )
    return session_id


def delete_typing_session(conn: sqlite3.Connection, session_id: int) -> None:
    """Delete one typing session with associated stats in single transaction."""
    with conn:
        conn.execute("DELETE FROM key_stats WHERE session_id = ?;", (session_id,))
        conn.execute("DELETE FROM bigram_stats WHERE session_id = ?;", (session_id,))
        conn.execute("DELETE FROM typing_sessions WHERE id = ?;", (session_id,))
    conn.commit()


def get_best(conn: sqlite3.Connection) -> float | None:
    """Return max net WPM or None when no sessions, excluding drills."""
    row = conn.execute("SELECT MAX(net_wpm) FROM typing_sessions WHERE mode != 'drill';").fetchone()
    return float(row[0]) if (row and row[0] is not None) else None


def get_7day_avg(conn: sqlite3.Connection) -> float | None:
    """Return avg net WPM for last 7 days or None, excluding drills."""
    cutoff: str = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    row = conn.execute(
        "SELECT AVG(net_wpm) FROM typing_sessions WHERE ts >= ? AND mode != 'drill';",
        (cutoff,),
    ).fetchone()
    return float(row[0]) if (row and row[0] is not None) else None


def get_header_stats(conn: sqlite3.Connection) -> tuple[float | None, int]:
    """Return Best WPM and solved count from one connection."""
    best: float | None = get_best(conn)
    row = conn.execute("SELECT COUNT(*) FROM lc_progress WHERE status='solved';").fetchone()
    solved: int = int(row[0]) if row and row[0] is not None else 0
    return (best, solved)


def _header_text(best: float | None, solved: int) -> str:
    """Format Best and Solved one-liner."""
    best_txt: str = f"{best:.1f} WPM" if best is not None else "--"
    return f"Best: {best_txt} | Solved: {solved}"


def get_cached_header(db_path: str | Path) -> str:
    """Return cached header text, refresh via single conn after TTL."""
    key: str = str(db_path)
    if not key:
        return _header_text(None, 0)
    now: float = time.monotonic()
    hit = _HEADER_CACHE.get(key)
    if hit is not None and (now - hit[0]) < HEADER_TTL_S:
        return hit[1]
    try:
        conn = get_db(Path(key))
    except OSError:
        return _header_text(None, 0)
    try:
        text = _header_text(*get_header_stats(conn))
    finally:
        conn.close()
    _HEADER_CACHE[key] = (now, text)
    return text


def clear_header_cache() -> None:
    """Clear cached header entries."""
    _HEADER_CACHE.clear()
