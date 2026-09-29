"""Headless GUI tests with dummy SDL and mocked network."""

import os as _os

_os.environ["SDL_VIDEODRIVER"] = "dummy"
_os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import sqlite3
import types
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pygame
import pytest

from idle import config
from idle.db import get_db
from idle.db import save_typing_session
from idle.gui import app as gui_app
from idle.gui import screens_lc
from idle.gui import screens_menu
from idle.gui import screens_stats
from idle.gui import screens_typing
from idle.gui import theme
from idle.gui.state import AppState
from idle.gui.state import Screen
from idle.gui.widgets import Button
from idle.gui.widgets import ScrollableList
from idle.gui.widgets import Textbox
from idle.typing.engine import calc_accuracy
from idle.typing.engine import calc_net_wpm
from idle.typing.engine import calc_raw_wpm


def _keydown(key: int, mod: int = 0) -> Any:
    """Build fake KEYDOWN event."""
    return types.SimpleNamespace(type=pygame.KEYDOWN, key=key, mod=mod)


def _textinput(chunk: str) -> Any:
    """Build fake TEXTINPUT event."""
    return types.SimpleNamespace(type=pygame.TEXTINPUT, text=chunk)


def _ensure_pygame() -> None:
    """Init pygame font for headless draws."""
    if not pygame.get_init():
        pygame.init()
    if not pygame.font.get_init():
        pygame.font.init()


def _tmp_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, Path, Path]:
    """Point resolve_paths at tmp dir, return paths."""
    db_path: Path = tmp_path / "idle.db"
    cfg_path: Path = tmp_path / "config.toml"
    auth_path: Path = tmp_path / "auth.json"
    monkeypatch.setattr(
        config, "resolve_paths", lambda: (db_path, cfg_path, auth_path)
    )
    return (db_path, cfg_path, auth_path)


def _sample_problems() -> list[dict[str, Any]]:
    """Return 3 rows for filter tests."""
    return [
        {
            "id": "1",
            "slug": "two-sum",
            "title": "Two Sum",
            "difficulty": "Easy",
            "tags": ["array"],
            "status": "todo",
            "ac_rate": 50.0,
        },
        {
            "id": "2",
            "slug": "add-two-numbers",
            "title": "Add Two Numbers",
            "difficulty": "Medium",
            "tags": ["linked-list"],
            "status": "todo",
            "ac_rate": 40.0,
        },
        {
            "id": "3",
            "slug": "hard-prob",
            "title": "Hard Prob",
            "difficulty": "Hard",
            "tags": ["dp"],
            "status": "ac",
            "ac_rate": 30.0,
        },
    ]


def _sample_detail() -> dict[str, Any]:
    """Return detail dict for load and action tests."""
    return {
        "question_id": "1",
        "id": "1",
        "slug": "two-sum",
        "title": "Two Sum",
        "difficulty": "Easy",
        "content_html": "<p>Given array.</p>",
        "code_snippets": {"python3": "def solve():\n    pass\n"},
        "sample_test_case": "[1,2]\n",
        "example_testcases": "[1,2]",
        "tags": ["array"],
        "ac_rate": 50.0,
    }


def _accepted_verdict() -> dict[str, Any]:
    """Return Accepted verdict with runtime and memory."""
    return {
        "status_msg": "Accepted",
        "status_runtime": "20 ms",
        "runtime_percentile": 90.0,
        "status_memory": "15 MB",
        "memory_percentile": 80.0,
    }


def test_theme_tokens() -> None:
    assert theme.BG == (10, 10, 12)
    assert theme.CORRECT == (74, 222, 128)
    assert theme.WRONG == (248, 113, 113)
    assert theme.LOGICAL_W == 960
    assert theme.LOGICAL_H == 640
    assert theme.FPS == 60
    assert theme.KEYBINDS["delete_word"] == "Ctrl+W"


def test_theme_get_font_headless() -> None:
    _ensure_pygame()
    font: Any = theme.get_font(20)
    assert font.get_linesize() > 0


def test_state_round_trip_all_screens() -> None:
    state: AppState = AppState()
    for screen in Screen:
        state.push(screen)
    for screen in reversed(list(Screen)):
        assert state.screen == screen
        state.pop()
    assert state.screen == Screen.MENU


def test_state_pop_empty_stays() -> None:
    state: AppState = AppState()
    assert state.pop() == Screen.MENU
    assert state.screen == Screen.MENU


def test_textbox_typing_and_backspace() -> None:
    _ensure_pygame()
    box: Textbox = Textbox()
    box.handle_key(_textinput("hi"))
    assert box.text == "hi"
    assert box.caret == 2
    box.handle_key(_keydown(pygame.K_BACKSPACE))
    assert box.text == "h"


def test_textbox_ctrl_w_deletes_word() -> None:
    _ensure_pygame()
    box: Textbox = Textbox(text="hello world")
    box.handle_key(_keydown(pygame.K_w, pygame.KMOD_CTRL))
    assert box.text == "hello "
    box.handle_key(_textinput("there"))
    assert box.text == "hello there"


def test_textbox_multiline_enter() -> None:
    _ensure_pygame()
    multi: Textbox = Textbox(multiline=True)
    multi.handle_key(_textinput("a"))
    multi.handle_key(_keydown(pygame.K_RETURN))
    assert multi.text == "a\n"
    single: Textbox = Textbox()
    single.handle_key(_keydown(pygame.K_RETURN))
    assert single.confirmed is True


def test_scrollable_list_move_and_confirm() -> None:
    _ensure_pygame()
    view: ScrollableList = ScrollableList(["a", "b", "c"], visible_count=2)
    assert view.selected_item() == "a"
    view.move(1)
    assert view.selected_item() == "b"
    view.move(10)
    assert view.selected_item() == "c"
    assert view.handle_key(_keydown(pygame.K_RETURN)) == "confirm"
    view.handle_key(_keydown(pygame.K_UP))
    assert view.selected_item() == "b"


def test_button_focus_flag() -> None:
    plain: Button = Button("ok", focused=False)
    focused: Button = Button("ok", focused=True)
    assert plain.focused is False
    assert focused.focused is True


def test_typing_parity_with_engine() -> None:
    text: str = "hello"
    session: screens_typing.TypingSession = screens_typing.new_session(text)
    now: float = 100.0
    for i, ch in enumerate(text):
        screens_typing._run_session(session, ch, now + float(i))
    out: dict[str, Any] = screens_typing.finalize_result(
        session, now + 60.0
    )
    elapsed: float = screens_typing.session_elapsed(session, now + 60.0)
    raw: float = calc_raw_wpm(session.total, elapsed)
    assert out["raw_wpm"] == pytest.approx(raw)
    assert out["accuracy"] == pytest.approx(calc_accuracy(5, 5))
    net: float = calc_net_wpm(raw, 0, elapsed)
    assert out["net_wpm"] == pytest.approx(net)


def test_typing_stop_on_error_blocks() -> None:
    session: screens_typing.TypingSession = screens_typing.new_session(
        "ab", stop_on_error=True
    )
    ok: bool = screens_typing._run_session(session, "x", 1.0)
    assert ok is False
    assert session.typed == []
    assert session.total == 1


def test_typing_backspace_and_word_delete() -> None:
    session: screens_typing.TypingSession = screens_typing.new_session(
        "hello world test"
    )
    for ch in "hello world":
        screens_typing._run_session(session, ch, 1.0)
    screens_typing.apply_backspace(session)
    assert "".join(session.typed) == "hello worl"
    screens_typing.apply_word_delete(session)
    assert "".join(session.typed) == "hello "


def test_typing_save_and_refresh_tmp_db(tmp_path: Path) -> None:
    conn: sqlite3.Connection = get_db(tmp_path / "idle.db")
    try:
        session: screens_typing.TypingSession = screens_typing.new_session(
            "hi"
        )
        screens_typing._run_session(session, "h", 1.0)
        screens_typing._run_session(session, "i", 2.0)
        screens_typing.finish_session(session, 62.0)
        sid: int | None = screens_typing.save_and_refresh(session, conn)
        assert sid is not None and sid >= 1
        assert session.best is not None
    finally:
        conn.close()


def test_menu_header_tmp_db(tmp_path: Path) -> None:
    conn: sqlite3.Connection = get_db(tmp_path / "idle.db")
    try:
        save_typing_session(
            conn,
            mode="time",
            duration_s=60.0,
            net_wpm=70.0,
            raw_wpm=75.0,
            accuracy=0.9,
            consistency=0.9,
            text_len=100,
            per_key={},
            per_bigram={},
        )
        conn.execute(
            "INSERT INTO lc_progress(problem_id, status) VALUES(1, 'solved');"
        )
        conn.commit()
        header: str = screens_menu.load_header(tmp_path / "idle.db")
        assert "70.0" in header
        assert "Solved: 1" in header
    finally:
        conn.close()


def test_menu_keyboard_nav() -> None:
    _ensure_pygame()
    selected: int
    target: Screen | None
    quit_flag: bool
    selected, target, quit_flag = screens_menu.handle_menu(
        _keydown(pygame.K_DOWN), 0
    )
    assert selected == 1
    assert quit_flag is False
    selected, target, quit_flag = screens_menu.handle_menu(
        _keydown(pygame.K_3), 0
    )
    assert target == Screen.LC_LIST
    _, _, quit_flag = screens_menu.handle_menu(
        _keydown(pygame.K_ESCAPE), 0
    )
    assert quit_flag is True


def test_lc_list_refresh_mocked() -> None:
    _ensure_pygame()
    view: screens_lc.LcListState = screens_lc.LcListState()
    with patch(
        "idle.lc.api.fetch_problem_list", return_value=_sample_problems()
    ):
        screens_lc.refresh_problem_list(view)
    assert len(view.problems) == 3
    assert view.needs_login is False
    assert view.items.selected_item() is not None


def test_lc_filters_apply() -> None:
    rows: list[dict[str, Any]] = screens_lc.apply_lc_filters(
        _sample_problems(), "Easy", None, None, 20
    )
    assert len(rows) == 1
    assert rows[0]["slug"] == "two-sum"


def test_lc_detail_load_mocked() -> None:
    with (
        patch(
            "idle.lc.api.fetch_problem_list",
            return_value=_sample_problems(),
        ),
        patch("idle.lc.api.fetch_question", return_value=_sample_detail()),
    ):
        detail, text, message, login = screens_lc.load_detail("two-sum")
    assert login is False
    assert detail is not None
    assert "Two Sum" in text
    assert "Given array" in text
    assert message == ""


def test_lc_flow_test_action_mocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tmp_paths(tmp_path, monkeypatch)
    detail: dict[str, Any] = _sample_detail()
    with patch("idle.lc.api.run_sample", return_value=_accepted_verdict()):
        result, panel, login = screens_lc.run_test_action(
            detail, "def solve():\n    pass\n", "[1,2]\n"
        )
    assert login is False
    assert result is not None
    assert "Accepted" in panel
    assert "runtime" in panel
    assert "memory" in panel


def test_lc_flow_submit_action_mocked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _tmp_paths(tmp_path, monkeypatch)
    detail: dict[str, Any] = _sample_detail()
    with (
        patch(
            "idle.lc.api.submit_solution",
            return_value={"submission_id": 7},
        ),
        patch("idle.lc.api.poll_verdict", return_value=_accepted_verdict()),
    ):
        verdict, panel, login, solved = screens_lc.run_submit_action(
            detail, "def solve():\n    pass\n"
        )
    assert login is False
    assert solved is True
    assert verdict is not None
    assert "Accepted" in panel


def test_lc_login_empty_and_save() -> None:
    ok: bool
    msg: str
    ok, msg = screens_lc.try_save_login("", "")
    assert ok is False
    with patch("idle.lc.auth.save_auth") as saved:
        ok, msg = screens_lc.try_save_login("dummy-session", "dummy-csrf")
    assert ok is True
    assert msg == "saved login"
    assert saved.call_count == 1
    assert "dummy-session" not in msg


def test_app_stack_esc_back() -> None:
    _ensure_pygame()
    state: AppState = AppState(db_path="")
    rt: gui_app._Runtime = gui_app._Runtime(state=state)
    rt.state.push(Screen.STATS)
    assert rt.state.screen == Screen.STATS
    gui_app._go_back(rt)
    assert rt.state.screen == Screen.MENU
    gui_app._go_back(rt)
    assert rt.state.screen == Screen.MENU


def test_app_menu_esc_quits() -> None:
    _ensure_pygame()
    state: AppState = AppState(db_path="")
    rt: gui_app._Runtime = gui_app._Runtime(state=state)
    assert gui_app._handle_current(_keydown(pygame.K_ESCAPE), rt) is True


def test_app_stats_esc_back() -> None:
    _ensure_pygame()
    state: AppState = AppState(db_path="")
    rt: gui_app._Runtime = gui_app._Runtime(state=state)
    rt.state.push(Screen.STATS)
    gui_app._handle_current(_keydown(pygame.K_ESCAPE), rt)
    assert rt.state.screen == Screen.MENU


def test_cli_defaults_to_gui(monkeypatch: pytest.MonkeyPatch) -> None:
    from idle import cli

    calls: list[Any] = []

    def _fake(argv: Any = None) -> int:
        calls.append(argv)
        return 0

    monkeypatch.setattr("idle.gui.app.run_gui", _fake)
    assert cli.main([]) == 0
    assert cli.main(["gui"]) == 0
    assert len(calls) == 2


def test_stats_empty_friendly(tmp_path: Path) -> None:
    data: dict[str, Any] = screens_stats.load_stats(tmp_path / "idle.db")
    assert data["recent"] == []
    assert data["best"] is None
    lines: list[str] = screens_stats._stat_lines(data)
    assert any("no sessions yet" in line for line in lines)


def test_draw_smoke_headless() -> None:
    _ensure_pygame()
    surface: Any = pygame.Surface((theme.LOGICAL_W, theme.LOGICAL_H))
    font: Any = theme.get_font(20)
    state: AppState = AppState()
    screens_menu.draw_menu(surface, state, 0, "Best: -- | Solved: 0")
    typing: screens_typing.TypingSession = screens_typing.new_typing_session(
        "hi there"
    )
    screens_typing.draw_typing(surface, state, typing)
    view: screens_lc.LcListState = screens_lc.LcListState()
    view.problems = _sample_problems()
    screens_lc.draw_lc_list(surface, font, view)
    detail_view: screens_lc.LcDetailState = screens_lc.make_detail_state(
        _sample_detail(), "line1\nline2", "two-sum"
    )
    screens_lc.draw_lc_detail(surface, font, detail_view)
    solve_view: screens_lc.LcSolveState = screens_lc.make_solve_state(
        _sample_detail()
    )
    screens_lc.draw_lc_solve(surface, font, solve_view)
    empty: dict[str, Any] = {
        "recent": [],
        "best": None,
        "avg": None,
        "by_diff": {},
        "attempts": [],
        "streak": 0,
        "active": 0,
    }
    screens_stats.draw_stats(surface, state, empty)
