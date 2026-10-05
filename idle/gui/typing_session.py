"""TypingSession dataclass, session creation, and lifecycle operations."""

from dataclasses import dataclass, field
from typing import Any

from idle.gui.typing_stats import (
    finish_session,
    session_elapsed,
)
from idle.typing.engine import Keystroke
from idle.typing.engine import update_stats

__all__: list[str] = [
    "IDLE_PAUSE_THRESHOLD",
    "TypingSession",
    "apply_backspace",
    "apply_word_delete",
    "check_finished",
    "is_finished",
    "new_drill_session",
    "new_session",
    "new_typing_session",
    "restart_session",
    "run_session_char",
]

IDLE_PAUSE_THRESHOLD: float = 2.5


@dataclass
class TypingSession:
    """Mutable typing state with metrics and result."""

    text: str = ""
    mode: str = "time"
    stop_on_error: bool = False
    limit_s: float = 60.0
    timed: bool = True
    typed: list[str] = field(default_factory=list)
    per_key: dict[str, dict[str, float]] = field(default_factory=dict)
    per_bigram: dict[str, dict[str, float]] = field(default_factory=dict)
    correct: int = 0
    total: int = 0
    start_ts: float | None = None
    last_ts: float | None = None
    spark: list[float] = field(default_factory=list)
    spark_sec: int = -1
    chars_prev_sec: int = 0
    paused_duration: float = 0.0
    finished: bool = False
    result: dict[str, Any] | None = None
    best: float | None = None
    seven_day_avg: float | None = None
    difficulty: str = "Easy"
    session_id: int | None = None


def new_session(
    text: str,
    mode: str = "time",
    stop_on_error: bool = False,
    limit_s: float = 60.0,
    timed: bool = True,
    difficulty: str = "Easy",
) -> TypingSession:
    """Create fresh session for given text."""
    return TypingSession(
        text=text,
        mode=mode,
        stop_on_error=stop_on_error,
        limit_s=limit_s,
        timed=timed,
        difficulty=difficulty,
    )


def new_typing_session(
    text: str,
    mode: str = "time",
    stop_on_error: bool = False,
    limit_s: float = 60.0,
    difficulty: str = "Easy",
) -> TypingSession:
    """Create typing session with timed flag from mode."""
    return new_session(
        text, mode, stop_on_error, limit_s, timed=(mode == "time"), difficulty=difficulty
    )


def new_drill_session(
    text: str, stop_on_error: bool = False, difficulty: str = "Easy"
) -> TypingSession:
    """Create untimed drill session for given text."""
    return new_session(text, "drill", stop_on_error, 0.0, timed=False, difficulty=difficulty)


def run_session_char(session: TypingSession, ch: str, now: float) -> bool:
    """Fold one char with stop_on_error block, return ok."""
    pos: int = len(session.typed)
    if pos >= len(session.text):
        return False
    exp: str = session.text[pos]
    last: float | None = session.last_ts
    if last is not None and (now - last) > IDLE_PAUSE_THRESHOLD:
        session.paused_duration += now - last
        lat: float = 0.0
    elif last is not None:
        lat = (now - last) * 1000.0
    else:
        lat = 0.0
    ok: bool = ch == exp
    session.total += 1
    if ok:
        session.correct += 1
    prev: str | None = session.typed[-1] if session.typed else None
    if session.start_ts is None:
        session.start_ts = now
    update_stats(Keystroke(ch, exp, lat, ok), session.per_key, session.per_bigram, prev)
    session.last_ts = now
    if session.stop_on_error and not ok:
        return False
    session.typed.append(ch)
    return ok


def apply_backspace(session: TypingSession) -> None:
    """Delete one typed char, keep counts."""
    if session.typed:
        session.typed.pop()


def apply_word_delete(session: TypingSession) -> None:
    """Delete to previous space like Ctrl+W."""
    while session.typed and session.typed[-1] == " ":
        session.typed.pop()
    while session.typed and session.typed[-1] != " ":
        session.typed.pop()


def is_finished(session: TypingSession, now: float) -> bool:
    """Return True on timeout or full text typed."""
    if session.start_ts is not None and session.timed:
        if session_elapsed(session, now) >= session.limit_s:
            return True
    return len(session.text) > 0 and len(session.typed) >= len(session.text)


def restart_session(session: TypingSession) -> None:
    """Clear typed stats, keep text and options."""
    session.typed = []
    session.per_key = {}
    session.per_bigram = {}
    session.correct = 0
    session.total = 0
    session.start_ts = None
    session.last_ts = None
    session.spark = []
    session.spark_sec = -1
    session.chars_prev_sec = 0
    session.paused_duration = 0.0
    session.finished = False
    session.result = None
    session.session_id = None


def check_finished(session: TypingSession, now: float) -> None:
    """Finalize session when timeout or text complete."""
    if not session.finished and is_finished(session, now):
        finish_session(session, now)
