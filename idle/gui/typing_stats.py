"""Typing session metrics computation, statistics, and persistence."""

import sqlite3
import time
from typing import TYPE_CHECKING, Any

from idle.db import get_7day_avg
from idle.db import get_best
from idle.db import save_typing_session
from idle.typing.engine import calc_accuracy
from idle.typing.engine import calc_consistency
from idle.typing.engine import calc_raw_wpm
from idle.typing.screen import format_results

if TYPE_CHECKING:
    from idle.gui.typing_session import TypingSession

__all__: list[str] = [
    "finalize_result",
    "finish_session",
    "result_lines",
    "sample_spark",
    "save_and_refresh",
    "session_elapsed",
    "session_header",
    "session_net_wpm",
    "session_progress",
]

IDLE_PAUSE_THRESHOLD: float = 2.5


def session_elapsed(session: "TypingSession", now: float) -> float:
    """Return active seconds since first keypress, pausing if idle > 2.5s."""
    if session.start_ts is None:
        return 0.0
    last: float = session.last_ts if session.last_ts is not None else session.start_ts
    idle_time: float = now - last
    effective_now: float = last if idle_time > IDLE_PAUSE_THRESHOLD else now
    return max(0.0, effective_now - session.start_ts - session.paused_duration)


def _uncorrected_count(session: "TypingSession") -> int:
    """Count typed positions differing from text."""
    bad: int = 0
    for i, ch in enumerate(session.typed):
        if i >= len(session.text) or ch != session.text[i]:
            bad += 1
    return bad


def session_net_wpm(session: "TypingSession", now: float) -> float:
    """Return live net WPM from correct chars."""
    elapsed: float = session_elapsed(session, now)
    return calc_raw_wpm(session.correct, elapsed) if elapsed > 0 else 0.0


def session_progress(session: "TypingSession") -> float:
    """Return 0-100 progress percent."""
    return (len(session.typed) / len(session.text) * 100.0) if session.text else 0.0


def session_header(session: "TypingSession", now: float) -> str:
    """Build live header with WPM elapsed progress."""
    net: float = session_net_wpm(session, now)
    elapsed: float = session_elapsed(session, now)
    pct: float = session_progress(session)
    if session.timed:
        return f"WPM {net:.1f} | {elapsed:.0f}/{session.limit_s:.0f}s | {pct:.0f}%"
    return f"WPM {net:.1f} | {elapsed:.0f}s | {pct:.0f}%"


def sample_spark(session: "TypingSession", now: float) -> None:
    """Append instantaneous WPM once per elapsed second."""
    elapsed: float = session_elapsed(session, now)
    sec: int = int(elapsed)
    if sec >= 1 and sec > session.spark_sec:
        session.spark_sec = sec
        chars_in_sec: int = session.correct - session.chars_prev_sec
        session.chars_prev_sec = session.correct
        instant: float = max(0.0, (chars_in_sec / 5.0) * 60.0)
        session.spark.append(instant)


def finalize_result(session: "TypingSession", now: float) -> dict[str, Any]:
    """Build result dict with WPM accuracy spark per-key."""
    elapsed: float = session_elapsed(session, now)
    net: float = calc_raw_wpm(session.correct, elapsed) if elapsed > 0 else 0.0
    spark: list[float] = list(session.spark) if session.spark else [net]
    return {
        "net_wpm": net,
        "raw_wpm": calc_raw_wpm(session.total, elapsed),
        "accuracy": calc_accuracy(session.correct, session.total),
        "consistency": calc_consistency(spark),
        "per_key": dict(session.per_key),
        "per_bigram": dict(session.per_bigram),
        "spark": spark,
        "elapsed_s": elapsed,
        "typed_chars": session.total,
        "correct": session.correct,
        "total": session.total,
        "uncorrected_errors": _uncorrected_count(session),
    }


def finish_session(session: "TypingSession", now: float) -> dict[str, Any]:
    """Mark finished and store result dict."""
    out: dict[str, Any] = finalize_result(session, now)
    session.finished = True
    session.result = out
    return out


def save_and_refresh(session: "TypingSession", conn: sqlite3.Connection) -> int | None:
    """Persist session and refresh Best and 7-day."""
    if session.total <= 0:
        return None
    if session.result is None:
        session.result = finalize_result(session, time.monotonic())
    res: dict[str, Any] = session.result
    sid: int = save_typing_session(
        conn,
        mode=session.mode,
        duration_s=float(res.get("elapsed_s", 0.0)),
        net_wpm=float(res.get("net_wpm", 0.0)),
        raw_wpm=float(res.get("raw_wpm", 0.0)),
        accuracy=float(res.get("accuracy", 0.0)),
        consistency=float(res.get("consistency", 0.0)),
        text_len=len(session.text),
        per_key=dict(res.get("per_key", {})),
        per_bigram=dict(res.get("per_bigram", {})),
    )
    session.best = get_best(conn)
    session.seven_day_avg = get_7day_avg(conn)
    session.session_id = sid
    return sid


def result_lines(session: "TypingSession") -> list[str]:
    """Format results with sparkline slowest missed Best 7-day."""
    res: dict[str, Any] = session.result or {}
    lines: list[str] = format_results(res, session.best, session.seven_day_avg)
    lines.append("Tab/Enter restart  Esc back")
    return lines
