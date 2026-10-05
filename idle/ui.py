"""Curses helpers with lazy imports and small-screen guards."""

from typing import Any

COLOR_CORRECT: int = 1
COLOR_WRONG: int = 2
COLOR_DIM: int = 3


def init_colors() -> None:
    """Init green/red/dim pairs, no-op when unsupported."""
    try:
        import curses

        if not curses.has_colors():
            return
        try:
            curses.start_color()
        except curses.error:
            return
        try:
            curses.use_default_colors()
        except curses.error:
            pass
        try:
            curses.init_pair(COLOR_CORRECT, curses.COLOR_GREEN, -1)
            curses.init_pair(COLOR_WRONG, curses.COLOR_RED, -1)
            curses.init_pair(COLOR_DIM, curses.COLOR_WHITE, -1)
        except curses.error:
            pass
    except (ImportError, Exception):
        pass


def safe_addstr(stdscr: Any, y: int, x: int, s: str) -> None:
    """Add string, ignoring errors from small screens."""
    try:
        stdscr.addstr(y, x, s)
    except Exception:
        pass


def require_min_size(stdscr: Any, h: int, w: int) -> bool:
    """Check terminal size, caller shows message when False."""
    try:
        max_y, max_x = stdscr.getmaxyx()
        return max_y >= h and max_x >= w
    except Exception:
        return False
