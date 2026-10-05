"""Typing session state tracking, timings, and input metrics calculation."""

import time
from typing import Any

from idle.typing.engine import (
    Keystroke,
    calc_accuracy,
    calc_consistency,
    calc_raw_wpm,
    update_stats,
)

__all__: list[str] = [
    "PAUSE_THRESHOLD",
    "backspace_state",
    "elapsed_seconds",
    "finalize_metrics",
    "finish_session",
    "handle_state_char",
    "is_session_done",
    "is_time_mode",
    "net_wpm_for",
    "new_state",
    "record_keypress",
    "restart_state",
    "sample_sparkline",
    "stop_on_error_mode",
    "time_limit_from_opts",
    "word_delete_state",
]

PAUSE_THRESHOLD: float = 2.5


def time_limit_from_opts(opts: dict[str, Any]) -> float:
    """Return session duration in seconds from opts."""
    for k in ("duration_s", "time", "default_time"):
        v: Any = opts.get(k)
        if isinstance(v, (int, float)) and float(v) > 0:
            return float(v)
    return 60.0


def stop_on_error_mode(opts: dict[str, Any]) -> bool:
    """Return True when strict mode blocks caret advance."""
    return bool(opts.get("stop_on_error", False))


def is_time_mode(opts: dict[str, Any]) -> bool:
    """Return True for timed session modes."""
    return str(opts.get("mode", "time")) == "time"


def new_state() -> dict[str, Any]:
    """Return fresh mutable loop state dictionary."""
    return {
        "typed": [],
        "per_key": {},
        "per_bigram": {},
        "correct": 0,
        "total": 0,
        "start_ts": None,
        "last_ts": None,
        "spark": [],
        "spark_sec": -1,
        "chars_prev_sec": 0,
        "paused_duration": 0.0,
    }


def elapsed_seconds(state: dict[str, Any], now: float) -> float:
    """Return active seconds since first keypress, pausing if idle > 2.5s."""
    start: float | None = state.get("start_ts")
    if start is None:
        return 0.0
    last: float = float(state["last_ts"]) if state.get("last_ts") is not None else start
    idle: float = now - last
    eff_now: float = last if idle > PAUSE_THRESHOLD else now
    return max(0.0, eff_now - start - float(state.get("paused_duration", 0.0)))


def sample_sparkline(state: dict[str, Any], net: float, elapsed: float) -> None:
    """Append instantaneous WPM once per elapsed second."""
    sec: int = int(elapsed)
    if sec >= 1 and sec > int(state.get("spark_sec", -1)):
        state["spark_sec"] = sec
        curr: int = int(state.get("correct", 0))
        prev: int = int(state.get("chars_prev_sec", 0))
        state["chars_prev_sec"] = curr
        state["spark"].append(max(0.0, ((curr - prev) / 5.0) * 60.0))


def net_wpm_for(state: dict[str, Any], text: str, elapsed: float) -> float:
    """Return net WPM from correct chars."""
    return calc_raw_wpm(int(state.get("correct", 0)), elapsed) if elapsed > 0 else 0.0


def record_keypress(state: dict[str, Any], ch: str, exp: str, now: float) -> bool:
    """Fold one char press into stats, return correctness."""
    last: float | None = state["last_ts"]
    lat: float = 0.0
    if last is not None:
        if (now - last) > PAUSE_THRESHOLD:
            state["paused_duration"] = float(state.get("paused_duration", 0.0)) + (now - last)
        else:
            lat = (now - last) * 1000.0
    ok: bool = ch == exp
    state["total"] += 1
    if ok:
        state["correct"] += 1
    if state["start_ts"] is None:
        state["start_ts"] = now
    prev = str(state["typed"][-1]) if state["typed"] else None
    update_stats(Keystroke(ch, exp, lat, ok), state["per_key"], state["per_bigram"], prev)
    state["last_ts"] = now
    return ok


def backspace_state(state: dict[str, Any]) -> None:
    """Delete one char, keeping error counts."""
    if state["typed"]:
        state["typed"].pop()


def word_delete_state(state: dict[str, Any]) -> None:
    """Delete to previous space like Ctrl+W."""
    t: list[str] = state["typed"]
    while t and t[-1] == " ":
        t.pop()
    while t and t[-1] != " ":
        t.pop()


def finalize_metrics(text: str, state: dict[str, Any], elapsed: float) -> dict[str, Any]:
    """Build result dict with WPM accuracy spark per-key bigrams."""
    tot, cor = int(state["total"]), int(state["correct"])
    net = calc_raw_wpm(cor, elapsed) if elapsed > 0 else 0.0
    spark = list(state["spark"]) if state["spark"] else [net]
    bad = sum(1 for i, ch in enumerate(state["typed"]) if i >= len(text) or ch != text[i])
    return {
        "net_wpm": net,
        "raw_wpm": calc_raw_wpm(tot, elapsed),
        "accuracy": calc_accuracy(cor, tot),
        "consistency": calc_consistency(spark),
        "per_key": dict(state["per_key"]),
        "per_bigram": dict(state["per_bigram"]),
        "spark": spark,
        "elapsed_s": elapsed,
        "typed_chars": tot,
        "correct": cor,
        "total": tot,
        "uncorrected_errors": bad,
    }


def handle_state_char(
    text: str, state: dict[str, Any], key: int, now: float, stop: bool
) -> None:
    """Apply printable key with stop-on-error blocking advance."""
    ch, pos = chr(key), len(state["typed"])
    if pos >= len(text):
        return
    exp = text[pos]
    if stop and ch != exp:
        record_keypress(state, ch, exp, now)
        return
    record_keypress(state, ch, exp, now)
    state["typed"].append(ch)


def restart_state(state: dict[str, Any]) -> None:
    """Reset state for Tab/Enter/Ctrl+R restart."""
    state.clear()
    state.update(new_state())


def is_session_done(
    state: dict[str, Any], text: str, timed: bool, limit: float, elapsed: float
) -> bool:
    """Return True when timeout or text complete."""
    if state["start_ts"] is not None and timed and elapsed >= limit:
        return True
    return len(text) > 0 and len(state["typed"]) >= len(text)


def finish_session(text: str, state: dict[str, Any], quit_flag: bool) -> dict[str, Any]:
    """Build final dict with completion flags."""
    out = finalize_metrics(text, state, elapsed_seconds(state, time.monotonic()))
    out["completed"], out["quit"] = not quit_flag, quit_flag
    return out
