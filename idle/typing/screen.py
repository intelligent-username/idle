"""Curses typing loop and plain results printer."""

import time
from typing import Any

from idle.typing.engine import Keystroke
from idle.typing.engine import calc_accuracy
from idle.typing.engine import calc_consistency
from idle.typing.engine import calc_net_wpm
from idle.typing.engine import calc_raw_wpm
from idle.typing.engine import update_stats

MIN_H = 10
MIN_W = 40
SPARK_BLOCKS = "▁▂▃▄▅▆▇█"
QUIT_KEY = 27
WORD_DELETE_KEY = 23
RESTART_KEYS = (9, 10)


def _time_limit(opts: dict[str, Any]) -> float:
    """Return session seconds from opts."""
    for key in ("duration_s", "time", "default_time"):
        val = opts.get(key)
        if isinstance(val, (int, float)) and float(val) > 0:
            return float(val)
    return 60.0


def _stop_on_error(opts: dict[str, Any]) -> bool:
    """Return True when strict mode blocks advance."""
    return bool(opts.get("stop_on_error", False))


def _is_time_mode(opts: dict[str, Any]) -> bool:
    """Return True for timed sessions."""
    mode = str(opts.get("mode", "time"))
    return mode == "time"


def _sparkline(values: list[float]) -> str:
    """Map values to block chars normalized by min-max.

    Test: _sparkline([0.0, 50.0, 100.0]) == "▁▅█".
    """
    if not values:
        return ""
    lo = min(values)
    hi = max(values)
    if hi <= lo:
        return SPARK_BLOCKS[0] * len(values)
    out: list[str] = []
    last = len(SPARK_BLOCKS) - 1
    for v in values:
        ratio = (v - lo) / (hi - lo)
        out.append(SPARK_BLOCKS[int(round(ratio * last))])
    return "".join(out)


def _avg_lat(entry: dict[str, float]) -> float:
    """Return average latency for one per-key entry."""
    attempts = float(entry.get("attempts", 0.0))
    if attempts <= 0:
        return 0.0
    return float(entry.get("total_latency_ms", 0.0)) / attempts


def _miss_rate(entry: dict[str, float]) -> float:
    """Return misses over attempts for one entry."""
    attempts = float(entry.get("attempts", 0.0))
    if attempts <= 0:
        return 0.0
    return float(entry.get("misses", 0.0)) / attempts


def _slowest(per_key: dict[str, dict[str, float]], n: int = 5) -> list[tuple[str, float]]:
    """Return top-n chars by average latency."""
    ranked = sorted(per_key.items(), key=lambda kv: _avg_lat(kv[1]), reverse=True)
    return [(k, _avg_lat(v)) for k, v in ranked[:n]]


def _most_missed(per_key: dict[str, dict[str, float]], n: int = 5) -> list[tuple[str, float]]:
    """Return top-n chars by miss rate."""
    ranked = sorted(per_key.items(), key=lambda kv: _miss_rate(kv[1]), reverse=True)
    return [(k, _miss_rate(v)) for k, v in ranked[:n]]


def _header(net: float, elapsed: float, limit: float, pos: int, total: int) -> str:
    """Build live header with WPM elapsed progress."""
    pct = (pos / total * 100.0) if total > 0 else 0.0
    return f"WPM {net:.1f} | {elapsed:.0f}/{limit:.0f}s | {pct:.0f}%"


def _new_state() -> dict[str, Any]:
    """Return fresh mutable loop state."""
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
    }


def _elapsed(state: dict[str, Any], now: float) -> float:
    """Return seconds since first keypress."""
    start = state["start_ts"]
    if start is None:
        return 0.0
    return max(0.0, now - float(start))


def _sample_spark(state: dict[str, Any], net: float, elapsed: float) -> None:
    """Append net WPM once per elapsed second."""
    sec = int(elapsed)
    if sec > int(state["spark_sec"]):
        state["spark_sec"] = sec
        state["spark"].append(net)


def _uncorrected(text: str, typed: list[str]) -> int:
    """Count positions where typed differs from text."""
    bad = 0
    for i, ch in enumerate(typed):
        if i >= len(text) or ch != text[i]:
            bad += 1
    return bad


def _net_for(state: dict[str, Any], text: str, elapsed: float) -> float:
    """Return net WPM from state and uncorrected errors.

    Test: state with total=300 correct after 60s gives net near 60.
    """
    raw = calc_raw_wpm(state["total"], elapsed)
    bad = _uncorrected(text, state["typed"])
    return calc_net_wpm(raw, bad, elapsed)


def _record_press(state: dict[str, Any], ch: str, exp: str, now: float) -> bool:
    """Fold one char press into stats, return correctness."""
    last = state["last_ts"]
    lat = (now - float(last)) * 1000.0 if last is not None else 0.0
    ok = ch == exp
    state["total"] += 1
    if ok:
        state["correct"] += 1
    typed_list: list[str] = state["typed"]
    prev = typed_list[-1] if typed_list else None
    if state["start_ts"] is None:
        state["start_ts"] = now
    prev_s = str(prev) if prev is not None else None
    update_stats(Keystroke(ch, exp, lat, ok), state["per_key"], state["per_bigram"], prev_s)
    state["last_ts"] = now
    return ok


def _backspace(state: dict[str, Any]) -> None:
    """Delete one char, keeping error counts."""
    typed_list: list[str] = state["typed"]
    if typed_list:
        typed_list.pop()


def _word_delete(state: dict[str, Any]) -> None:
    """Delete to previous space like Ctrl+W."""
    typed_list: list[str] = state["typed"]
    while typed_list and typed_list[-1] == " ":
        typed_list.pop()
    while typed_list and typed_list[-1] != " ":
        typed_list.pop()


def _draw_header(stdscr: Any, header: str) -> None:
    """Write live header row safely."""
    from idle.ui import safe_addstr

    width = stdscr.getmaxyx()[1]
    safe_addstr(stdscr, 0, 0, header[: max(0, width - 1)])


def _cell_map(text: str, width: int) -> list[tuple[int, str, int, int]]:
    """Map each char to wrapped row col.

    Test: _cell_map("ab", 10)[1] == (1, "b", 2, 1).
    """
    cells: list[tuple[int, str, int, int]] = []
    row = 2
    col = 0
    for i, exp in enumerate(text):
        if exp == "\n":
            row += 1
            col = 0
            continue
        if col >= width:
            row += 1
            col = 0
        cells.append((i, exp, row, col))
        col += 1
    return cells


def _draw_body(stdscr: Any, text: str, typed: list[str], width: int) -> tuple[int, int]:
    """Draw wrapped chars, return cursor yx."""
    pos = len(typed)
    cur = (2, 0)
    for i, exp, row, col in _cell_map(text, width):
        if i == pos:
            cur = (row, col)
        _put(stdscr, row, col, exp, _color_for(i, typed, text))
    if pos >= len(text):
        last = _cell_map(text, width)
        if last:
            cur = (last[-1][2], last[-1][3] + 1)
    return cur


def _draw(stdscr: Any, text: str, state: dict[str, Any], header: str) -> tuple[int, int]:
    """Render header plus wrapped text, return cursor yx.

    Test: fake stdscr collecting addstr gets header and text rows.
    """
    import curses

    try:
        stdscr.clear()
    except Exception:
        pass
    _draw_header(stdscr, header)
    width = max(1, stdscr.getmaxyx()[1])
    cur = _draw_body(stdscr, text, state["typed"], width)
    try:
        stdscr.move(cur[0], cur[1])
    except Exception:
        pass
    try:
        stdscr.refresh()
    except Exception:
        pass
    _ = curses.A_NORMAL
    return cur


def _color_for(i: int, typed: list[str], text: str) -> int:
    """Pick color id for position i."""
    from idle.ui import COLOR_CORRECT
    from idle.ui import COLOR_DIM
    from idle.ui import COLOR_WRONG

    if i >= len(typed):
        return COLOR_DIM
    return COLOR_CORRECT if typed[i] == text[i] else COLOR_WRONG


def _put(stdscr: Any, y: int, x: int, ch: str, color: int) -> None:
    """Write one char with color, ignore small screen errors."""
    import curses

    try:
        stdscr.addstr(y, x, ch, curses.color_pair(color))
    except Exception:
        try:
            from idle.ui import safe_addstr

            safe_addstr(stdscr, y, x, ch)
        except Exception:
            pass


def _is_backspace(key: int, curses_mod: Any) -> bool:
    """Return True for backspace key codes."""
    return key in (8, 127, getattr(curses_mod, "KEY_BACKSPACE", 263))


def _finalize(text: str, state: dict[str, Any], elapsed: float) -> dict[str, Any]:
    """Build result dict with WPM accuracy spark per-key bigrams.

    Test: _finalize("hi", fresh state, 60.0) has net/raw/accuracy keys.
    """
    total = int(state["total"])
    correct = int(state["correct"])
    raw = calc_raw_wpm(total, elapsed)
    bad = _uncorrected(text, state["typed"])
    net = calc_net_wpm(raw, bad, elapsed)
    spark: list[float] = list(state["spark"])
    if not spark:
        spark = [net]
    consistency = calc_consistency(spark)
    accuracy = calc_accuracy(correct, total)
    return {
        "net_wpm": net,
        "raw_wpm": raw,
        "accuracy": accuracy,
        "consistency": consistency,
        "per_key": dict(state["per_key"]),
        "per_bigram": dict(state["per_bigram"]),
        "spark": spark,
        "elapsed_s": elapsed,
        "typed_chars": total,
        "correct": correct,
        "total": total,
        "uncorrected_errors": bad,
    }


def _handle_char(text: str, state: dict[str, Any], key: int, now: float, stop: bool) -> None:
    """Apply printable key with stop-on-error blocking advance."""
    ch = chr(key)
    pos = len(state["typed"])
    if pos >= len(text):
        return
    exp = text[pos]
    if stop and ch != exp:
        _record_press(state, ch, exp, now)
        return
    _record_press(state, ch, exp, now)
    state["typed"].append(ch)


def _restart(state: dict[str, Any]) -> None:
    """Reset state for Tab Enter restart."""
    fresh = _new_state()
    state.clear()
    state.update(fresh)


def _is_done(state: dict[str, Any], text: str, timed: bool, limit: float, elapsed: float) -> bool:
    """Return True when timeout or text complete."""
    if state["start_ts"] is not None and timed and elapsed >= limit:
        return True
    total = len(text)
    return total > 0 and len(state["typed"]) >= total


def _read_key(stdscr: Any) -> int:
    """Read one key, return -1 when idle."""
    try:
        return int(stdscr.getch())
    except Exception:
        return -1


def _dispatch_key(text: str, state: dict[str, Any], key: int, stop: bool, curses_mod: Any) -> str:
    """Apply one key, return quit restart or handled."""
    if key == QUIT_KEY:
        return "quit"
    if key in RESTART_KEYS:
        _restart(state)
        return "restart"
    if key == getattr(curses_mod, "KEY_RESIZE", 410):
        return "resize"
    if _is_backspace(key, curses_mod):
        _backspace(state)
        return "edit"
    if key == WORD_DELETE_KEY:
        _word_delete(state)
        return "edit"
    if 32 <= key <= 126:
        _handle_char(text, state, key, time.monotonic(), stop)
        return "char"
    return "ignore"


def _setup_input(stdscr: Any) -> None:
    """Enable keypad and timeout for live loop."""
    try:
        stdscr.timeout(100)
    except Exception:
        pass


def _finish(text: str, state: dict[str, Any], quit_flag: bool) -> dict[str, Any]:
    """Build final dict with completion flags."""
    out = _finalize(text, state, _elapsed(state, time.monotonic()))
    out["completed"] = not quit_flag
    out["quit"] = quit_flag
    return out


def _loop(stdscr: Any, text: str, opts: dict[str, Any]) -> dict[str, Any]:
    """Run input loop until timeout done or Esc quit.

    Test: fake stdscr feeding Esc returns dict with net_wpm key.
    """
    import curses

    limit = _time_limit(opts)
    stop = _stop_on_error(opts)
    timed = _is_time_mode(opts)
    state = _new_state()
    quit_flag = False
    _setup_input(stdscr)
    while True:
        now = time.monotonic()
        elapsed = _elapsed(state, now)
        net = _net_for(state, text, elapsed)
        _sample_spark(state, net, elapsed)
        total = len(text)
        pos = len(state["typed"])
        _draw(stdscr, text, state, _header(net, elapsed, limit, pos, total))
        if _is_done(state, text, timed, limit, elapsed):
            break
        key = _read_key(stdscr)
        if key == -1:
            continue
        if _dispatch_key(text, state, key, stop, curses) == "quit":
            quit_flag = True
            break
    return _finish(text, state, quit_flag)


def run_typing_test(stdscr: Any, text: str, opts: dict[str, Any]) -> dict[str, Any]:
    """Run curses typing test, return metrics dict.

    Test: fake stdscr with getmaxyx (12, 60) and getch Esc gives net_wpm.
    """
    from idle.ui import init_colors
    from idle.ui import require_min_size

    if not require_min_size(stdscr, MIN_H, MIN_W):
        return {"error": "terminal too small"}
    init_colors()
    try:
        stdscr.keypad(True)
    except Exception:
        pass
    try:
        return _loop(stdscr, text, opts)
    finally:
        try:
            stdscr.keypad(False)
        except Exception:
            pass
        try:
            stdscr.nodelay(False)
        except Exception:
            pass


def show_results(
    result: dict[str, Any],
    best: float | None = None,
    seven_day_avg: float | None = None,
) -> None:
    """Print Net Raw Acc Consistency sparkline slowest missed Best 7-day.

    Test: show_results({"net_wpm": 50.0, "spark": [1.0]}) prints Net.
    """
    if best is None and isinstance(result.get("best"), (int, float)):
        best = float(result["best"])
    if seven_day_avg is None:
        for key in ("seven_day_avg", "avg7", "avg_7day"):
            val = result.get(key)
            if isinstance(val, (int, float)):
                seven_day_avg = float(val)
                break
    net = float(result.get("net_wpm", 0.0))
    raw = float(result.get("raw_wpm", 0.0))
    acc = float(result.get("accuracy", 0.0))
    cons = float(result.get("consistency", 0.0))
    spark_vals = [float(v) for v in result.get("spark", [])]
    per_key = result.get("per_key", {})
    print(f"Net WPM: {net:.1f}")
    print(f"Raw WPM: {raw:.1f}")
    print(f"Accuracy: {acc * 100.0:.1f}%")
    print(f"Consistency: {cons * 100.0:.1f}%")
    print(f"Sparkline: {_sparkline(spark_vals)}")
    _print_slowest(per_key)
    _print_missed(per_key)
    if best is None:
        print("Best: --")
    else:
        print(f"Best: {best:.1f} WPM")
    if seven_day_avg is None:
        print("7-day: --")
    else:
        print(f"7-day: {seven_day_avg:.1f} WPM")


def _print_slowest(per_key: dict[str, dict[str, float]]) -> None:
    """Print top-5 slowest keys by average latency."""
    rows = _slowest(per_key, 5)
    if not rows:
        print("Slowest: --")
        return
    parts = [f"{_disp(k)} {v:.0f}ms" for k, v in rows]
    print("Slowest: " + ", ".join(parts))


def _print_missed(per_key: dict[str, dict[str, float]]) -> None:
    """Print top-5 most missed keys by miss rate."""
    rows = _most_missed(per_key, 5)
    if not rows:
        print("Most missed: --")
        return
    parts = [f"{_disp(k)} {v * 100.0:.0f}%" for k, v in rows]
    print("Most missed: " + ", ".join(parts))


def _disp(ch: str) -> str:
    """Show space key visibly."""
    if ch == " ":
        return "space"
    return ch
