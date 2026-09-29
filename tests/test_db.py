"""DB tests using tmp_path only."""

import sqlite3
from pathlib import Path

from idle.db import SCHEMA_VERSION
from idle.db import get_7day_avg
from idle.db import get_best
from idle.db import get_db
from idle.db import migrate
from idle.db import save_typing_session

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


def _sample_key() -> dict[str, dict[str, float]]:
    return {
        "a": {"attempts": 10.0, "misses": 2.0, "total_latency_ms": 500.0},
        "b": {"attempts": 5.0, "misses": 0.0, "total_latency_ms": 250.0},
    }


def _sample_bigram() -> dict[str, dict[str, float]]:
    return {"ab": {"count": 3.0, "total_latency_ms": 150.0}}


def _save(
    conn: sqlite3.Connection, net_wpm: float = 60.0
) -> int:
    return save_typing_session(
        conn,
        mode="time",
        duration_s=60.0,
        net_wpm=net_wpm,
        raw_wpm=65.0,
        accuracy=0.95,
        consistency=0.9,
        text_len=300,
        per_key=_sample_key(),
        per_bigram=_sample_bigram(),
    )


def test_save_typing_session_persists(tmp_path: Path) -> None:
    conn: sqlite3.Connection = get_db(tmp_path / "idle.db")
    try:
        session_id: int = _save(conn, net_wpm=60.0)
        assert session_id >= 1
        row = conn.execute(
            "SELECT mode, net_wpm, text_len FROM typing_sessions WHERE id = ?;",
            (session_id,),
        ).fetchone()
        assert row[0] == "time"
        assert float(row[1]) == 60.0
        assert int(row[2]) == 300
        keys = conn.execute(
            "SELECT COUNT(*) FROM key_stats WHERE session_id = ?;",
            (session_id,),
        ).fetchone()
        assert int(keys[0]) == 2
        bigrams = conn.execute(
            "SELECT COUNT(*) FROM bigram_stats WHERE session_id = ?;",
            (session_id,),
        ).fetchone()
        assert int(bigrams[0]) == 1
    finally:
        conn.close()


def test_save_empty_stats_still_inserts_session(tmp_path: Path) -> None:
    conn: sqlite3.Connection = get_db(tmp_path / "idle.db")
    try:
        session_id: int = save_typing_session(
            conn,
            mode="words",
            duration_s=30.0,
            net_wpm=40.0,
            raw_wpm=42.0,
            accuracy=1.0,
            consistency=1.0,
            text_len=150,
            per_key={},
            per_bigram={},
        )
        count = conn.execute(
            "SELECT COUNT(*) FROM typing_sessions;"
        ).fetchone()
        assert int(count[0]) == 1
        assert session_id >= 1
    finally:
        conn.close()


def test_get_best_returns_max(tmp_path: Path) -> None:
    conn: sqlite3.Connection = get_db(tmp_path / "idle.db")
    try:
        assert get_best(conn) is None
        _save(conn, net_wpm=50.0)
        _save(conn, net_wpm=80.0)
        best: float | None = get_best(conn)
        assert best == 80.0
    finally:
        conn.close()


def test_get_7day_avg_filters_old(tmp_path: Path) -> None:
    from datetime import datetime
    from datetime import timedelta
    from datetime import timezone

    conn: sqlite3.Connection = get_db(tmp_path / "idle.db")
    try:
        assert get_7day_avg(conn) is None
        _save(conn, net_wpm=60.0)
        _save(conn, net_wpm=90.0)
        old_ts: str = (
            datetime.now(timezone.utc) - timedelta(days=8)
        ).isoformat()
        conn.execute(
            "INSERT INTO typing_sessions"
            "(ts, mode, duration_s, net_wpm, raw_wpm,"
            " accuracy, consistency, text_len)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
            (old_ts, "time", 60.0, 10.0, 12.0, 0.9, 0.9, 200),
        )
        conn.commit()
        avg: float | None = get_7day_avg(conn)
        assert avg == 75.0
    finally:
        conn.close()
