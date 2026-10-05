"""Input handling and key event dispatching for GUI typing and drills."""

import time
from typing import Any

from idle.gui.typing_session import (
    TypingSession,
    apply_backspace,
    apply_word_delete,
    check_finished,
    restart_session,
    run_session_char,
)
from idle.gui.typing_stats import sample_spark

__all__: list[str] = [
    "handle_drill",
    "handle_session_key",
    "handle_typing",
]


def _handle_results_key(event: Any, session: TypingSession) -> str | None:
    """Handle Tab Enter Ctrl+R restart and Esc back on results screen."""
    import pygame

    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        return None
    key: int = int(getattr(event, "key", 0))
    mod: int = int(getattr(event, "mod", 0))
    ctrl: bool = bool(mod & pygame.KMOD_CTRL)
    if key == pygame.K_ESCAPE:
        return "back"
    if (ctrl and key == pygame.K_r) or key in (
        pygame.K_TAB,
        pygame.K_RETURN,
        pygame.K_KP_ENTER,
    ):
        restart_session(session)
        return "restart"
    return None


def _handle_textinput(event: Any, session: TypingSession, now: float) -> str | None:
    """Fold TEXTINPUT chunk into session."""
    chunk: str = str(getattr(event, "text", ""))
    for ch in chunk:
        if ch in ("\r", "\t", "\x12"):
            continue
        run_session_char(session, ch, now)
    sample_spark(session, now)
    check_finished(session, now)
    return "finished" if session.finished else None


def _handle_edit_key(key: int, ctrl: bool, session: TypingSession) -> bool:
    """Apply backspace or Ctrl+W, return True if handled."""
    import pygame

    if ctrl and key == pygame.K_w:
        apply_word_delete(session)
        return True
    if key == pygame.K_BACKSPACE:
        if ctrl:
            apply_word_delete(session)
        else:
            apply_backspace(session)
        return True
    return False


def _handle_return_key(key: int, session: TypingSession, now: float) -> str | None:
    """Fold newline when text expects it."""
    import pygame

    if key not in (pygame.K_RETURN, pygame.K_KP_ENTER) or "\n" not in session.text:
        return None
    run_session_char(session, "\n", now)
    sample_spark(session, now)
    check_finished(session, now)
    return "finished" if session.finished else None


def _handle_keydown(event: Any, session: TypingSession, now: float) -> str | None:
    """Route KEYDOWN edits, return, restart or back."""
    import pygame

    key: int = int(getattr(event, "key", 0))
    mod: int = int(getattr(event, "mod", 0))
    ctrl: bool = bool(mod & pygame.KMOD_CTRL)
    if key == pygame.K_ESCAPE:
        return "back"
    if ctrl and key == pygame.K_r:
        return "restart"
    if _handle_edit_key(key, ctrl, session):
        return None
    return _handle_return_key(key, session, now)


def _handle_live_key(event: Any, session: TypingSession, now: float) -> str | None:
    """Apply backspace Ctrl+W chars, return back or None."""
    import pygame

    etype: int = int(getattr(event, "type", -1))
    if etype == pygame.TEXTINPUT:
        return _handle_textinput(event, session, now)
    if etype == pygame.KEYDOWN:
        return _handle_keydown(event, session, now)
    return None


def handle_session_key(event: Any, session: TypingSession) -> str | None:
    """Shared key router for typing and drill."""
    now: float = time.monotonic()
    if session.finished:
        return _handle_results_key(event, session)
    return _handle_live_key(event, session, now)


def handle_typing(event: Any, session: TypingSession) -> str | None:
    """Handle typing event, return back restart finished or None."""
    return handle_session_key(event, session)


def handle_drill(event: Any, session: TypingSession) -> str | None:
    """Handle drill event via shared session runner."""
    return handle_session_key(event, session)
