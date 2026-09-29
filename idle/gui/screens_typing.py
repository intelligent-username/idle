"""Typing and drill pygame screens with CLI parity (lazy pygame)."""

import random
import sqlite3
import time
from dataclasses import dataclass, field
from typing import Any

from idle.db import get_7day_avg
from idle.db import get_best
from idle.db import save_typing_session
from idle.typing.drill import generate_drill_text
from idle.typing.drill import score_keys
from idle.typing.engine import calc_accuracy
from idle.typing.engine import calc_consistency
from idle.typing.engine import calc_net_wpm
from idle.typing.engine import calc_raw_wpm
from idle.typing.engine import Keystroke
from idle.typing.engine import update_stats
from idle.typing.screen import _most_missed
from idle.typing.screen import _slowest
from idle.typing.screen import _sparkline
from idle.typing.texts import load_words
from idle.typing.texts import make_text

__all__: list[str] = [
    "TypingSession",
    "new_session",
    "build_typing_text",
    "build_drill_text",
    "new_typing_session",
    "new_drill_session",
    "draw_typing",
    "handle_typing",
    "draw_drill",
    "handle_drill",
]

MARGIN: int = 32
TOP_Y: int = 64
MAX_W: int = 896
FONT_SIZE: int = 20
SMALL_SIZE: int = 16


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
    finished: bool = False
    result: dict[str, Any] | None = None
    best: float | None = None
    seven_day_avg: float | None = None


def new_session(
    text: str,
    mode: str = "time",
    stop_on_error: bool = False,
    limit_s: float = 60.0,
    timed: bool = True,
) -> TypingSession:
    """Create fresh session for given text."""
    return TypingSession(
        text=text,
        mode=mode,
        stop_on_error=stop_on_error,
        limit_s=limit_s,
        timed=timed,
    )


def build_typing_text(
    mode: str = "time",
    word_list: int = 200,
    num_words: int = 50,
    punct: bool = False,
    numbers: bool = False,
    language: str = "python",
    rng: random.Random | None = None,
    words: list[str] | None = None,
) -> str:
    """Build typing text via texts helpers.

    Test: build_typing_text("words", words=["hi","yo"],
    num_words=2, rng=Random(0)) returns 2 tokens.
    """
    gen: random.Random = rng if rng is not None else random.Random()
    if mode in ("time", "words"):
        source: list[str] = list(words) if words is not None else load_words(word_list)
        return make_text(
            mode,
            words=source,
            word_list=word_list,
            num_words=num_words,
            punct=punct,
            numbers=numbers,
            rng=gen,
        )
    if mode == "quote":
        return make_text("quote", rng=gen)
    if mode == "code":
        return make_text("code", language=language, rng=gen)
    raise ValueError(f"unknown mode {mode!r}")


def build_drill_text(
    conn: sqlite3.Connection, words: list[str], length: int = 30
) -> str:
    """Build drill text weighted to weak keys."""
    return generate_drill_text(conn, words, length)


def drill_weak_avg(conn: sqlite3.Connection) -> float | None:
    """Return mean of top weak scores or None.

    Test: empty conn gives None.
    """
    scores: dict[str, float] = score_keys(conn)
    if not scores:
        return None
    top: list[float] = sorted(scores.values(), reverse=True)[:12]
    if not top:
        return None
    return sum(top) / len(top)


def new_typing_session(
    text: str,
    mode: str = "time",
    stop_on_error: bool = False,
    limit_s: float = 60.0,
) -> TypingSession:
    """Create typing session with timed flag from mode."""
    return new_session(text, mode, stop_on_error, limit_s, timed=(mode == "time"))


def new_drill_session(text: str, stop_on_error: bool = False) -> TypingSession:
    """Create untimed drill session for given text."""
    return new_session(text, "drill", stop_on_error, 0.0, timed=False)


def _run_session(session: TypingSession, ch: str, now: float) -> bool:
    """Fold one char with stop_on_error block, return ok.

    Test: s=new_session("ab"); _run_session(s,"a",1.0)
    gives typed ["a"] and total 1.
    """
    pos: int = len(session.typed)
    if pos >= len(session.text):
        return False
    exp: str = session.text[pos]
    last: float | None = session.last_ts
    lat: float = (now - float(last)) * 1000.0 if last is not None else 0.0
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


def session_elapsed(session: TypingSession, now: float) -> float:
    """Return seconds since first keypress."""
    if session.start_ts is None:
        return 0.0
    return max(0.0, now - float(session.start_ts))


def _uncorrected_count(session: TypingSession) -> int:
    """Count typed positions differing from text."""
    bad: int = 0
    for i, ch in enumerate(session.typed):
        if i >= len(session.text) or ch != session.text[i]:
            bad += 1
    return bad


def session_net_wpm(session: TypingSession, now: float) -> float:
    """Return live net WPM from current typed buffer."""
    elapsed: float = session_elapsed(session, now)
    raw: float = calc_raw_wpm(session.total, elapsed)
    return calc_net_wpm(raw, _uncorrected_count(session), elapsed)


def session_progress(session: TypingSession) -> float:
    """Return 0-100 progress percent."""
    if not session.text:
        return 0.0
    return len(session.typed) / len(session.text) * 100.0


def session_header(session: TypingSession, now: float) -> str:
    """Build live header with WPM elapsed progress."""
    net: float = session_net_wpm(session, now)
    elapsed: float = session_elapsed(session, now)
    pct: float = session_progress(session)
    if session.timed:
        return f"WPM {net:.1f} | {elapsed:.0f}/{session.limit_s:.0f}s | {pct:.0f}%"
    return f"WPM {net:.1f} | {elapsed:.0f}s | {pct:.0f}%"


def sample_spark(session: TypingSession, now: float) -> None:
    """Append net WPM once per elapsed second."""
    elapsed: float = session_elapsed(session, now)
    sec: int = int(elapsed)
    if sec > session.spark_sec:
        session.spark_sec = sec
        session.spark.append(session_net_wpm(session, now))


def is_finished(session: TypingSession, now: float) -> bool:
    """Return True on timeout or full text typed."""
    if session.start_ts is not None and session.timed:
        if session_elapsed(session, now) >= session.limit_s:
            return True
    return len(session.text) > 0 and len(session.typed) >= len(session.text)


def finalize_result(session: TypingSession, now: float) -> dict[str, Any]:
    """Build result dict with WPM accuracy spark per-key.

    Test: s=new_session("hi"); _run_session(s,"h",1.0)
    then finalize_result(s, 61.0) has net_wpm key.
    """
    elapsed: float = session_elapsed(session, now)
    raw: float = calc_raw_wpm(session.total, elapsed)
    bad: int = _uncorrected_count(session)
    net: float = calc_net_wpm(raw, bad, elapsed)
    spark: list[float] = list(session.spark) if session.spark else [net]
    return {
        "net_wpm": net,
        "raw_wpm": raw,
        "accuracy": calc_accuracy(session.correct, session.total),
        "consistency": calc_consistency(spark),
        "per_key": dict(session.per_key),
        "per_bigram": dict(session.per_bigram),
        "spark": spark,
        "elapsed_s": elapsed,
        "typed_chars": session.total,
        "correct": session.correct,
        "total": session.total,
        "uncorrected_errors": bad,
    }


def finish_session(session: TypingSession, now: float) -> dict[str, Any]:
    """Mark finished and store result dict."""
    out: dict[str, Any] = finalize_result(session, now)
    session.finished = True
    session.result = out
    return out


def save_and_refresh(session: TypingSession, conn: sqlite3.Connection) -> int | None:
    """Persist session and refresh Best and 7-day.

    Test: fresh session with total 0 returns None.
    """
    if session.result is None or session.total <= 0:
        return None
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
    return sid


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
    session.finished = False
    session.result = None


def _disp(ch: str) -> str:
    """Show space key visibly."""
    return "space" if ch == " " else ch


def result_lines(session: TypingSession) -> list[str]:
    """Format results with sparkline slowest missed Best 7-day.

    Test: s=new_session("hi"); s.result=finalize_result(s, 60.0)
    then result_lines(s)[0] starts with "Net WPM".
    """
    res: dict[str, Any] = session.result or {}
    net: float = float(res.get("net_wpm", 0.0))
    raw: float = float(res.get("raw_wpm", 0.0))
    acc: float = float(res.get("accuracy", 0.0))
    cons: float = float(res.get("consistency", 0.0))
    spark_vals: list[float] = [float(v) for v in res.get("spark", [])]
    per_key: dict[str, dict[str, float]] = dict(res.get("per_key", {}))
    lines: list[str] = [
        f"Net WPM: {net:.1f}",
        f"Raw WPM: {raw:.1f}",
        f"Accuracy: {acc * 100.0:.1f}%",
        f"Consistency: {cons * 100.0:.1f}%",
        f"Sparkline: {_sparkline(spark_vals)}",
    ]
    lines.append(_slowest_line(per_key))
    lines.append(_missed_line(per_key))
    if session.best is None:
        lines.append("Best: --")
    else:
        lines.append(f"Best: {session.best:.1f} WPM")
    if session.seven_day_avg is None:
        lines.append("7-day: --")
    else:
        lines.append(f"7-day: {session.seven_day_avg:.1f} WPM")
    lines.append("Tab/Enter restart  Esc back")
    return lines


def _slowest_line(per_key: dict[str, dict[str, float]]) -> str:
    """Format top-5 slowest keys line."""
    rows: list[tuple[str, float]] = _slowest(per_key, 5)
    if not rows:
        return "Slowest: --"
    return "Slowest: " + ", ".join(f"{_disp(k)} {v:.0f}ms" for k, v in rows)


def _missed_line(per_key: dict[str, dict[str, float]]) -> str:
    """Format top-5 most missed keys line."""
    rows: list[tuple[str, float]] = _most_missed(per_key, 5)
    if not rows:
        return "Most missed: --"
    return "Most missed: " + ", ".join(f"{_disp(k)} {v * 100.0:.0f}%" for k, v in rows)


def _check_finished(session: TypingSession, now: float) -> None:
    """Finalize session when timeout or text complete."""
    if session.finished:
        return
    if is_finished(session, now):
        finish_session(session, now)


def _handle_results_key(event: Any, session: TypingSession) -> str | None:
    """Handle Tab Enter restart and Esc back on results."""
    import pygame

    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        return None
    key: int = int(getattr(event, "key", 0))
    if key == pygame.K_ESCAPE:
        return "back"
    if key in (pygame.K_TAB, pygame.K_RETURN, pygame.K_KP_ENTER):
        restart_session(session)
        return "restart"
    return None


def _handle_textinput(event: Any, session: TypingSession, now: float) -> str | None:
    """Fold TEXTINPUT chunk into session."""
    chunk: str = str(getattr(event, "text", ""))
    for ch in chunk:
        if ch in ("\r", "\t"):
            continue
        _run_session(session, ch, now)
    sample_spark(session, now)
    _check_finished(session, now)
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

    if key not in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return None
    if "\n" not in session.text:
        return None
    _run_session(session, "\n", now)
    sample_spark(session, now)
    _check_finished(session, now)
    return "finished" if session.finished else None


def _handle_unicode(event: Any, session: TypingSession, now: float) -> str | None:
    """Fold printable unicode fallback into session."""
    uni: str = str(getattr(event, "unicode", ""))
    if len(uni) != 1 or not uni.isprintable():
        return None
    _run_session(session, uni, now)
    sample_spark(session, now)
    _check_finished(session, now)
    return "finished" if session.finished else None


def _handle_keydown(event: Any, session: TypingSession, now: float) -> str | None:
    """Route KEYDOWN edits, return, unicode, or back."""
    import pygame

    key: int = int(getattr(event, "key", 0))
    mod: int = int(getattr(event, "mod", 0))
    ctrl: bool = bool(mod & pygame.KMOD_CTRL)
    if key == pygame.K_ESCAPE:
        return "back"
    if _handle_edit_key(key, ctrl, session):
        return None
    ret: str | None = _handle_return_key(key, session, now)
    if ret is not None:
        return ret
    return _handle_unicode(event, session, now)


def _handle_live_key(event: Any, session: TypingSession, now: float) -> str | None:
    """Apply backspace Ctrl+W chars, return back or None."""
    import pygame

    etype: int = int(getattr(event, "type", -1))
    if etype == pygame.TEXTINPUT:
        return _handle_textinput(event, session, now)
    if etype != pygame.KEYDOWN:
        return None
    return _handle_keydown(event, session, now)


def _handle_session_key(event: Any, session: TypingSession) -> str | None:
    """Shared key router for typing and drill.

    Test: s=new_session("ab"); e with TEXTINPUT "a"
    keeps session unstarted timer then started.
    """
    now: float = time.monotonic()
    if session.finished:
        return _handle_results_key(event, session)
    out: str | None = _handle_live_key(event, session, now)
    return out


def handle_typing(event: Any, session: TypingSession) -> str | None:
    """Handle typing event, return back restart finished or None."""
    return _handle_session_key(event, session)


def handle_drill(event: Any, session: TypingSession) -> str | None:
    """Handle drill event via shared session runner."""
    return _handle_session_key(event, session)


def _draw_header(surface: Any, font: Any, session: TypingSession) -> None:
    """Draw live WPM progress header at top."""
    header: str = session_header(session, time.monotonic())
    img = font.render(header, True, _fg())
    surface.blit(img, (MARGIN, 16))


def _fg() -> tuple[int, int, int]:
    """Return foreground color without pygame import."""
    from idle.gui import theme

    return theme.FG


def _char_color(i: int, session: TypingSession) -> tuple[int, int, int]:
    """Pick green red dim for position i."""
    from idle.gui import theme

    if i >= len(session.typed):
        return theme.DIM
    exp: str = session.text[i] if i < len(session.text) else ""
    return theme.CORRECT if session.typed[i] == exp else theme.WRONG


def _draw_chars(surface: Any, font: Any, session: TypingSession) -> tuple[int, int, int]:
    """Draw wrapped chars, return end x y plus line height."""
    from idle.gui import theme

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


def _draw_caret(surface: Any, x: int, y: int, line_h: int) -> None:
    """Draw cursor bar at x y."""
    import pygame

    from idle.gui import theme

    pygame.draw.line(surface, theme.FG, (x, y), (x, y + line_h), 1)


def _draw_body(surface: Any, font: Any, session: TypingSession) -> None:
    """Draw wrapped chars green red dim with caret.

    Test: headless dummy surface draws without error.
    """
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
    """Shared draw for typing and drill with title.

    Test: headless dummy surface draws without error.
    """
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
    _draw_session(surface, state, session, "Typing  Esc back")


def draw_drill(surface: Any, state: Any, session: TypingSession) -> None:
    """Draw drill session via shared runner."""
    _draw_session(surface, state, session, "Drill  Esc back")
