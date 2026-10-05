"""Pygame rendering functions for typing and drill screens."""

import time
from typing import Any

from idle.gui.typing_session import TypingSession
from idle.gui.typing_stats import result_lines, session_header

__all__: list[str] = [
    "FONT_SIZE",
    "MARGIN",
    "MAX_W",
    "SMALL_SIZE",
    "TOP_Y",
    "draw_drill",
    "draw_typing",
]

MARGIN: int = 32
TOP_Y: int = 64
MAX_W: int = 896
FONT_SIZE: int = 20
SMALL_SIZE: int = 16


def _fg() -> tuple[int, int, int]:
    """Return foreground color without top-level pygame import."""
    from idle.gui import theme

    return theme.FG


def _char_color(i: int, session: TypingSession) -> tuple[int, int, int]:
    """Pick green red dim for position i."""
    from idle.gui import theme

    if i >= len(session.typed):
        return theme.DIM
    exp: str = session.text[i] if i < len(session.text) else ""
    return theme.CORRECT if session.typed[i] == exp else theme.WRONG


def _draw_caret(surface: Any, x: int, y: int, line_h: int) -> None:
    """Draw cursor bar at (x, y)."""
    import pygame

    from idle.gui import theme

    pygame.draw.line(surface, theme.FG, (x, y), (x, y + line_h), 1)


def _draw_header(surface: Any, font: Any, session: TypingSession) -> None:
    """Draw live WPM progress header at top."""
    header: str = session_header(session, time.monotonic())
    img = font.render(header, True, _fg())
    surface.blit(img, (MARGIN, 16))


def _draw_chars(surface: Any, font: Any, session: TypingSession) -> tuple[int, int, int]:
    """Draw wrapped chars, return end x, y plus line height."""
    x: int = MARGIN
    y: int = TOP_Y
    line_h: int = font.get_linesize()
    pos: int = len(session.typed)
    for i, exp in enumerate(session.text):
        if exp == "\n":
            x = MARGIN
            y += line_h
            continue
        glyph_w: int = font.size(exp)[0]
        if x + glyph_w > MARGIN + MAX_W:
            x = MARGIN
            y += line_h
        img = font.render(exp, True, _char_color(i, session))
        surface.blit(img, (x, y))
        if i == pos:
            _draw_caret(surface, x, y, line_h)
        x += glyph_w
    return (x, y, line_h)


def _draw_body(surface: Any, font: Any, session: TypingSession) -> None:
    """Draw wrapped chars green red dim with caret."""
    _draw_header(surface, font, session)
    x: int
    y: int
    line_h: int
    x, y, line_h = _draw_chars(surface, font, session)
    if len(session.typed) >= len(session.text):
        _draw_caret(surface, x, y, line_h)


def _draw_results(surface: Any, font: Any, session: TypingSession) -> None:
    """Draw sparkline top-5 Best 7-day plus hint."""
    from idle.gui import theme

    surface.fill(theme.BG)
    y: int = MARGIN
    for line in result_lines(session):
        img = font.render(line, True, theme.FG)
        surface.blit(img, (MARGIN, y))
        y += font.get_linesize() + 2


def _draw_session(surface: Any, state: Any, session: TypingSession, title: str) -> None:
    """Shared draw for typing and drill with title."""
    import pygame

    from idle.gui import theme

    surface.fill(theme.BG)
    font = theme.get_font(FONT_SIZE)
    small = theme.get_font(SMALL_SIZE)
    title_img = small.render(title, True, theme.DIM)
    surface.blit(title_img, (MARGIN, 40))
    if session.finished:
        _draw_results(surface, font, session)
        return
    _draw_body(surface, font, session)
    msg: str = str(getattr(state, "message", "") or "")
    if msg:
        hint = small.render(msg, True, theme.ACCENT)
        surface.blit(hint, (MARGIN, 600))
    _ = pygame.Rect


def draw_typing(surface: Any, state: Any, session: TypingSession) -> None:
    """Draw typing session with live header and colors."""
    diff_tag: str = f" [{session.difficulty}]" if getattr(session, "difficulty", "") else ""
    _draw_session(surface, state, session, f"Typing{diff_tag}  Esc back")


def draw_drill(surface: Any, state: Any, session: TypingSession) -> None:
    """Draw drill session via shared runner."""
    diff_tag: str = f" [{session.difficulty}]" if getattr(session, "difficulty", "") else ""
    _draw_session(surface, state, session, f"Drill{diff_tag}  Esc back")
