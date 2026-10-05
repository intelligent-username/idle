"""Curses typing interface, UI event loop, and results dispatcher."""

import time
from typing import Any

from idle.typing.results import SPARK_BLOCKS, format_results, show_results
from idle.typing.state import (
    backspace_state,
    elapsed_seconds,
    finish_session,
    handle_state_char,
    is_session_done,
    is_time_mode,
    net_wpm_for,
    new_state,
    restart_state,
    sample_sparkline,
    stop_on_error_mode,
    time_limit_from_opts,
    word_delete_state,
)
from idle.ui import (
    COLOR_CORRECT,
    COLOR_DIM,
    COLOR_WRONG,
    init_colors,
    require_min_size,
    safe_addstr,
)

__all__: list[str] = [
    "MIN_H",
    "MIN_W",
    "QUIT_KEY",
    "RESTART_KEYS",
    "SPARK_BLOCKS",
    "WORD_DELETE_KEY",
    "format_results",
    "run_typing_test",
    "show_results",
]

MIN_H: int = 10
MIN_W: int = 40
QUIT_KEY: int = 27
WORD_DELETE_KEY: int = 23
RESTART_KEYS: tuple[int, ...] = (9, 10, 18)


def _header(net: float, elapsed: float, limit: float, pos: int, total: int) -> str:
    """Build live header string with WPM elapsed progress."""
    pct = (pos / total * 100.0) if total > 0 else 0.0
    return f"WPM {net:.1f} | {elapsed:.0f}/{limit:.0f}s | {pct:.0f}%"


def _cell_map(text: str, width: int) -> list[tuple[int, str, int, int]]:
    """Map each char to wrapped row/col coordinates."""
    cells: list[tuple[int, str, int, int]] = []
    row, col = 2, 0
    for i, exp in enumerate(text):
        if exp == "\n" or col >= width:
            row, col = row + 1, 0
            if exp == "\n":
                continue
        cells.append((i, exp, row, col))
        col += 1
    return cells


def _color_for(i: int, typed: list[str], text: str) -> int:
    """Pick color pair ID for position i."""
    if i >= len(typed):
        return COLOR_DIM
    return COLOR_CORRECT if typed[i] == text[i] else COLOR_WRONG


def _put(stdscr: Any, y: int, x: int, ch: str, color: int) -> None:
    """Write one char with color safely."""
    try:
        import curses

        stdscr.addstr(y, x, ch, curses.color_pair(color))
    except Exception:
        try:
            safe_addstr(stdscr, y, x, ch)
        except Exception:
            pass


def _draw_body(
    stdscr: Any,
    text: str,
    typed: list[str],
    width: int,
    cells: list[tuple[int, str, int, int]],
) -> tuple[int, int]:
    """Draw wrapped characters and return active cursor row/col."""
    pos = len(typed)
    cur = (2, 0)
    for i, exp, row, col in cells:
        if i == pos:
            cur = (row, col)
        _put(stdscr, row, col, exp, _color_for(i, typed, text))
    if pos >= len(text) and cells:
        cur = (cells[-1][2], cells[-1][3] + 1)
    return cur


def _draw(stdscr: Any, text: str, state: dict[str, Any], header: str) -> tuple[int, int]:
    """Render header and wrapped body text."""
    try:
        stdscr.clear()
    except Exception:
        pass
    w = max(1, stdscr.getmaxyx()[1])
    safe_addstr(stdscr, 0, 0, header[: max(0, w - 1)])
    cells = _cell_map(text, w)
    cur = _draw_body(stdscr, text, state["typed"], w, cells)
    try:
        stdscr.move(cur[0], cur[1])
        stdscr.refresh()
    except Exception:
        pass
    return cur


def _dispatch_key(text: str, state: dict[str, Any], key: int, stop: bool, curses_mod: Any) -> str:
    """Apply one keypress to state and return action code."""
    if key == QUIT_KEY:
        return "quit"
    if key in RESTART_KEYS:
        restart_state(state)
        return "restart"
    if key == getattr(curses_mod, "KEY_RESIZE", 410):
        return "resize"
    if key in (8, 127, getattr(curses_mod, "KEY_BACKSPACE", 263)):
        backspace_state(state)
        return "edit"
    if key == WORD_DELETE_KEY:
        word_delete_state(state)
        return "edit"
    if 32 <= key <= 126:
        handle_state_char(text, state, key, time.monotonic(), stop)
        return "char"
    return "ignore"


def _loop(stdscr: Any, text: str, opts: dict[str, Any]) -> dict[str, Any]:
    """Run curses input loop until timeout, completion, or quit."""
    import curses

    limit, stop, timed = time_limit_from_opts(opts), stop_on_error_mode(opts), is_time_mode(opts)
    state, quit_flag = new_state(), False
    try:
        stdscr.timeout(100)
    except Exception:
        pass
    while True:
        now = time.monotonic()
        el = elapsed_seconds(state, now)
        net = net_wpm_for(state, text, el)
        sample_sparkline(state, net, el)
        _draw(stdscr, text, state, _header(net, el, limit, len(state["typed"]), len(text)))
        if is_session_done(state, text, timed, limit, el):
            break
        try:
            k = int(stdscr.getch())
        except Exception:
            k = -1
        if k != -1 and _dispatch_key(text, state, k, stop, curses) == "quit":
            quit_flag = True
            break
    return finish_session(text, state, quit_flag)


def run_typing_test(stdscr: Any, text: str, opts: dict[str, Any]) -> dict[str, Any]:
    """Run curses typing test and return metrics dictionary."""
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
            stdscr.nodelay(False)
        except Exception:
            pass
