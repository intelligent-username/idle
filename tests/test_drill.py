"""Drill tests using tmp_path only."""

import random
import sqlite3
from pathlib import Path

from idle.db import get_db
from idle.typing.drill import generate_drill_text
from idle.typing.drill import score_keys


def _add_session(
    conn: sqlite3.Connection, keys: list[tuple[str, int, int, float]]
) -> int:
    cur = conn.execute(
        "INSERT INTO typing_sessions "
        "(ts, mode, duration_s, net_wpm, raw_wpm, accuracy, consistency, text_len) "
        "VALUES (?,?,?,?,?,?,?,?);",
        ("2026-01-01T00:00:00+00:00", "time", 60.0, 40.0, 45.0, 0.9, 0.8, 100),
    )
    sid: int = int(cur.lastrowid or 0)
    assert sid != 0
    for ch, att, miss, lat in keys:
        conn.execute(
            "INSERT INTO key_stats "
            "(session_id, char, attempts, misses, total_latency_ms) "
            "VALUES (?,?,?,?,?);",
            (sid, ch, att, miss, lat),
        )
    conn.commit()
    return sid


def _weak_db(path: Path) -> sqlite3.Connection:
    conn: sqlite3.Connection = get_db(path)
    for _ in range(5):
        _add_session(conn, [("z", 20, 12, 4000.0), ("e", 20, 1, 1000.0)])
    return conn


def test_weak_over_representation(tmp_path: Path) -> None:
    conn: sqlite3.Connection = _weak_db(tmp_path / "d1.db")
    try:
        scores: dict[str, float] = score_keys(conn)
        assert scores["z"] > scores["e"]
        random.seed(0)
        text: str = generate_drill_text(conn, ["zzz", "eee", "mmm"], length=30)
        parts: list[str] = text.split()
        assert len(parts) == 30
        assert parts.count("zzz") > parts.count("eee")
    finally:
        conn.close()


def test_fallback_uniform_when_few_sessions(tmp_path: Path) -> None:
    conn: sqlite3.Connection = get_db(tmp_path / "d2.db")
    try:
        random.seed(1)
        text: str = generate_drill_text(conn, ["alpha", "beta"], length=30)
        parts: list[str] = text.split()
        assert len(parts) == 30
        assert set(parts).issubset({"alpha", "beta"})
        assert score_keys(conn) == {}
    finally:
        conn.close()


def test_latency_influences_ranking(tmp_path: Path) -> None:
    conn: sqlite3.Connection = get_db(tmp_path / "d3.db")
    try:
        for _ in range(5):
            _add_session(conn, [("a", 20, 0, 1000.0), ("b", 20, 0, 5000.0)])
        scores: dict[str, float] = score_keys(conn)
        assert scores["b"] > scores["a"]
    finally:
        conn.close()
