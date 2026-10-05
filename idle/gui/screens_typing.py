"""Typing and drill pygame screens facade with text generation and helpers."""

import random
import sqlite3

from idle.gui.typing_input import handle_drill, handle_session_key, handle_typing
from idle.gui.typing_render import (
    FONT_SIZE,
    MARGIN,
    MAX_W,
    SMALL_SIZE,
    TOP_Y,
    draw_drill,
    draw_typing,
)
from idle.gui.typing_session import (
    IDLE_PAUSE_THRESHOLD,
    TypingSession,
    apply_backspace,
    apply_word_delete,
    is_finished,
    new_drill_session,
    new_session,
    new_typing_session,
    restart_session,
    run_session_char,
)
from idle.gui.typing_stats import (
    finalize_result,
    finish_session,
    result_lines,
    sample_spark,
    save_and_refresh,
    session_elapsed,
    session_header,
    session_net_wpm,
    session_progress,
)
from idle.typing.drill import generate_drill_text, weak_avg
from idle.typing.texts import (
    build_difficulty_typing_text,
    load_tiered_passages,
    load_words,
    make_text,
    rate_passage,
)

__all__: list[str] = [
    "FONT_SIZE",
    "IDLE_PAUSE_THRESHOLD",
    "MARGIN",
    "MAX_W",
    "SMALL_SIZE",
    "TOP_Y",
    "TypingSession",
    "apply_backspace",
    "apply_word_delete",
    "build_difficulty_typing_text",
    "build_drill_text",
    "build_typing_text",
    "draw_drill",
    "draw_typing",
    "drill_weak_avg",
    "finalize_result",
    "finish_session",
    "handle_drill",
    "handle_typing",
    "is_finished",
    "load_tiered_passages",
    "load_words",
    "new_drill_session",
    "new_session",
    "new_typing_session",
    "rate_passage",
    "restart_session",
    "result_lines",
    "save_and_refresh",
    "session_elapsed",
    "session_header",
    "session_net_wpm",
    "session_progress",
]

_run_session = run_session_char


def build_typing_text(
    mode: str = "time",
    word_list: int = 200,
    num_words: int = 50,
    punct: bool = False,
    numbers: bool = False,
    language: str = "python",
    rng: random.Random | None = None,
    words: list[str] | None = None,
    difficulty: int | None = None,
) -> str:
    """Build typing text via texts helpers or difficulty tiered passages."""
    gen: random.Random = rng if rng is not None else random.Random()
    if difficulty is not None:
        return build_difficulty_typing_text(difficulty, num_words=num_words, rng=gen)
    if mode in ("time", "words"):
        source: list[str] | None = list(words) if words is not None else None
        return make_text(
            mode,
            words=source,
            word_list=word_list,
            num_words=num_words,
            punct=punct,
            numbers=numbers,
            rng=gen,
        )
    if mode in ("quote", "passage", "passages"):
        return make_text(mode, rng=gen)
    if mode == "code":
        return make_text("code", language=language, rng=gen)
    raise ValueError(f"unknown mode {mode!r}")


def build_drill_text(
    conn: sqlite3.Connection,
    words: list[str],
    length: int = 30,
    weak_keys: int = 5,
    difficulty: int = 0,
) -> str:
    """Build drill text weighted to weak keys and difficulty."""
    return generate_drill_text(conn, words, length, weak_keys=weak_keys, difficulty=difficulty)


def drill_weak_avg(conn: sqlite3.Connection) -> float | None:
    """Return mean of top weak scores or None."""
    return weak_avg(conn)
