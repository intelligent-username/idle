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


def test_menu_difficulty_nav() -> None:
    _ensure_pygame()
    state = AppState()
    assert state.typing_difficulty == 0
    assert state.drill_difficulty == 0

    # Right arrow on row 0 increments typing difficulty
    screens_menu.handle_menu(_keydown(pygame.K_RIGHT), 0, state)
    assert state.typing_difficulty == 1

    # Left arrow wraps around to 4 (Master)
    screens_menu.handle_menu(_keydown(pygame.K_LEFT), 0, state)
    assert state.typing_difficulty == 0
    screens_menu.handle_menu(_keydown(pygame.K_LEFT), 0, state)
    assert state.typing_difficulty == 4

    # Navigate to drill (row 1) and test drill difficulty
    screens_menu.handle_menu(_keydown(pygame.K_RIGHT), 1, state)
    assert state.drill_difficulty == 1

    # Left/Right on row 2 does not change difficulties
    screens_menu.handle_menu(_keydown(pygame.K_RIGHT), 2, state)
    assert state.typing_difficulty == 4
    assert state.drill_difficulty == 1

    # Pressing 1 or 2 activates target screen
    _, target1, _ = screens_menu.handle_menu(_keydown(pygame.K_1), 2, state)
    assert target1 == Screen.TYPE
    _, target2, _ = screens_menu.handle_menu(_keydown(pygame.K_2), 2, state)
    assert target2 == Screen.DRILL


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
    with (
        patch(
            "idle.lc.auth.validate_session_cookies",
            return_value=(True, ""),
        ),
        patch("idle.lc.auth.save_auth") as saved,
    ):
        ok, msg = screens_lc.try_save_login("dummy-session", "dummy-csrf")
    assert ok is True
    assert msg == "saved login"
    assert saved.call_count == 1
    assert "dummy-session" not in msg


def test_try_login_password_passthrough_taxonomy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Each taxonomy message passes verbatim, no offline remap."""
    import idle.lc.auth as auth_mod

    msgs: list[str] = [
        "could not login (offline?). Check network and retry.",
        "login failed: HTTP 403 from LeetCode (retry later).",
        "LeetCode challenge detected (captcha/cloudflare). Retry later.",
        "login failed: could not find login token (page changed?)",
        "login failed: bad credentials or captcha",
    ]
    monkeypatch.setattr(auth_mod, "save_auth", lambda *a, **k: None)
    for msg in msgs:
        def _raise(u: str, p: str, _m: str = msg) -> dict[str, str]:
            raise RuntimeError(_m)

        monkeypatch.setattr(auth_mod, "login_username_password", _raise)
        ok, out = screens_lc.try_login_password("u", "p")
        assert ok is False
        assert out == msg


def test_try_login_password_empty_maps_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty exception message falls back to offline text."""
    import idle.lc.auth as auth_mod

    def _raise_empty(u: str, p: str) -> dict[str, str]:
        raise RuntimeError("")

    monkeypatch.setattr(auth_mod, "login_username_password", _raise_empty)
    monkeypatch.setattr(auth_mod, "save_auth", lambda *a, **k: None)
    ok, msg = screens_lc.try_login_password("u", "p")
    assert ok is False
    assert msg == "could not login (offline?). Check network and retry."


def test_network_message_preserves_taxonomy() -> None:
    """Taxonomy preserved, generic and empty map to offline."""
    keep: list[str] = [
        "login failed: bad credentials or captcha",
        "login failed: HTTP 403 from LeetCode (retry later).",
        "login failed: could not find login token (page changed?)",
        "LeetCode challenge detected (captcha/cloudflare). Retry later.",
    ]
    for msg in keep:
        assert screens_lc._network_message(RuntimeError(msg), "login") == msg
    assert screens_lc._network_message(RuntimeError("boom"), "login") == (
        "could not login (offline?). Check network and retry."
    )
    assert screens_lc._network_message(RuntimeError(""), "login") == (
        "could not login (offline?). Check network and retry."
    )


def test_try_save_login_verified_and_unverified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty, verified save, offline unverified save."""
    import idle.lc.auth as auth_mod

    ok, msg = screens_lc.try_save_login("", "")
    assert (ok, msg) == (False, screens_lc.LOGIN_EMPTY_MSG)
    monkeypatch.setattr(auth_mod, "save_auth", lambda *a, **k: None)
    monkeypatch.setattr(auth_mod, "validate_session_cookies", lambda c, timeout=10: (True, ""))
    ok, msg = screens_lc.try_save_login("sess123", "csrf123")
    assert (ok, msg) == (True, "saved login")
    assert "sess123" not in msg
    offline: str = "could not login (offline?). Check network and retry."
    monkeypatch.setattr(auth_mod, "validate_session_cookies", lambda c, timeout=10: (False, offline))
    ok, msg = screens_lc.try_save_login("sess123", "")
    assert (ok, msg) == (True, screens_lc.LOGIN_UNVERIFIED_MSG)


def test_handle_lc_login_cookie_mode_calls_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cookie mode Enter routes to try_save_login."""
    _ensure_pygame()
    view: screens_lc.LcLoginState = screens_lc.LcLoginState(
        mode="cookie", focus=1
    )
    view.session_box = Textbox(text="sess123")
    view.csrf_box = Textbox(text="csrf123")
    seen: dict[str, tuple[str, str]] = {}

    def _fake_save(sess: str, csrf: str) -> tuple[bool, str]:
        seen["args"] = (sess, csrf)
        return (True, "saved login")

    def _no_password(u: str, p: str) -> tuple[bool, str]:
        raise AssertionError("password path must not run in cookie mode")

    monkeypatch.setattr(screens_lc, "try_save_login", _fake_save)
    monkeypatch.setattr(screens_lc, "try_login_password", _no_password)
    result = screens_lc.handle_lc_login(_keydown(pygame.K_RETURN), view)
    assert result == "login_ok"
    assert seen["args"] == ("sess123", "csrf123")
    assert view.message == "saved login"
    assert view.saved is True
    assert view.session_box.text == ""
    assert view.csrf_box.text == ""


def test_handle_lc_login_password_mode_calls_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Password mode Enter routes to try_login_password."""
    _ensure_pygame()
    view: screens_lc.LcLoginState = screens_lc.LcLoginState(
        mode="password", focus=1
    )
    view.username_box = Textbox(text="bob")
    view.password_box = Textbox(text="pw123")
    seen: dict[str, tuple[str, str]] = {}

    def _fake_login(u: str, p: str) -> tuple[bool, str]:
        seen["args"] = (u, p)
        return (True, "saved login")

    def _no_save(sess: str, csrf: str) -> tuple[bool, str]:
        raise AssertionError("cookie path must not run in password mode")

    monkeypatch.setattr(screens_lc, "try_login_password", _fake_login)
    monkeypatch.setattr(screens_lc, "try_save_login", _no_save)
    result = screens_lc.handle_lc_login(_keydown(pygame.K_RETURN), view)
    assert result == "login_ok"
    assert seen["args"] == ("bob", "pw123")
    assert view.saved is True


def test_cmd_lc_catch_all_preserves_taxonomy(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """_cmd_lc prints taxonomy verbatim."""
    import argparse

    from idle import cli

    msgs: list[str] = [
        "login failed: HTTP 403 from LeetCode (retry later).",
        "LeetCode challenge detected (captcha/cloudflare). Retry later.",
        "login failed: bad credentials or captcha",
        "Session expired. Run: idle lc login",
        "saved login (unverified, offline?)",
        "login cancelled: empty session",
    ]
    for msg in msgs:
        def _raise(name: str, args: Any, _m: str = msg) -> None:
            raise RuntimeError(_m)

        monkeypatch.setattr(cli, "_dispatch_lc", _raise)
        cli._cmd_lc(argparse.Namespace(lc_command="login"))
        out: str = capsys.readouterr().out
        assert msg in out
        assert "could not complete lc command" not in out


def test_cmd_lc_generic_maps_offline(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Generic error maps to offline line."""
    import argparse

    from idle import cli

    def _raise_generic(name: str, args: Any) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(cli, "_dispatch_lc", _raise_generic)
    cli._cmd_lc(argparse.Namespace(lc_command="list"))
    out: str = capsys.readouterr().out
    assert out.strip() == "could not complete lc command (offline?). Check network and retry."


def test_make_login_state_autofill() -> None:
    with patch("idle.lc.auth.load_saved_credentials", return_value=("autouser", "autopass")):
        view = screens_lc.make_login_state()
    assert view.username_box.text == "autouser"
    assert view.password_box.text == "autopass"


def test_try_auto_login() -> None:
    with (
        patch("idle.lc.auth.load_auth", return_value=None),
        patch("idle.lc.auth.load_saved_credentials", return_value=("autouser", "autopass")),
        patch("idle.gui.screens_lc.try_login_password", return_value=(True, "saved login")),
    ):
        ok, msg = screens_lc.try_auto_login()
    assert ok is True
    assert msg == "saved login"


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


def _sample_result() -> dict[str, Any]:
    """Build result dict for format tests."""
    return {
        "net_wpm": 50.0,
        "raw_wpm": 55.0,
        "accuracy": 0.95,
        "consistency": 0.9,
        "spark": [40.0, 50.0, 60.0],
        "per_key": {
            "a": {"attempts": 10.0, "misses": 1.0, "total_latency_ms": 500.0},
        },
        "elapsed_s": 60.0,
    }


def test_format_results_headline() -> None:
    """format_results starts with Net WPM."""
    from idle.typing.screen import format_results

    lines: list[str] = format_results(_sample_result(), 50.0, 60.0)
    assert lines[0].startswith("Net WPM")
    assert any(line.startswith("Best: 50.0") for line in lines)
    assert any(line.startswith("7-Day Avg: 60.0") for line in lines)


def test_show_results_matches_format(capsys: Any) -> None:
    """show_results prints joined format_results."""
    from idle.typing.screen import format_results
    from idle.typing.screen import show_results

    result: dict[str, Any] = _sample_result()
    expected: list[str] = format_results(result, 50.0, 60.0)
    show_results(result, 50.0, 60.0)
    out: str = capsys.readouterr().out
    assert out == "\n".join(expected) + "\n"


def test_result_lines_reuses_format() -> None:
    """GUI result_lines equals format plus hint."""
    from idle.typing.screen import format_results

    session: screens_typing.TypingSession = screens_typing.new_session("hi")
    session.result = _sample_result()
    session.best = 50.0
    session.seven_day_avg = 60.0
    lines: list[str] = screens_typing.result_lines(session)
    expected: list[str] = format_results(session.result, 50.0, 60.0)
    assert lines[:-1] == expected
    assert lines[-1] == "Tab/Enter restart  Esc back"


def test_drill_weak_avg_delegates(tmp_path: Path) -> None:
    """GUI drill_weak_avg matches canonical weak_avg."""
    from idle.typing.drill import weak_avg

    conn: sqlite3.Connection = get_db(tmp_path / "gui_weak.db")
    try:
        assert screens_typing.drill_weak_avg(conn) is None
        assert weak_avg(conn) is None
    finally:
        conn.close()


class _FakeCurses:
    """Minimal stdscr double for draw tests."""

    def getmaxyx(self) -> tuple[int, int]:
        """Return fixed terminal size."""
        return (24, 80)

    def clear(self) -> None:
        """No-op clear."""
        return None

    def move(self, y: int, x: int) -> None:
        """No-op move."""
        return None

    def refresh(self) -> None:
        """No-op refresh."""
        return None

    def addstr(self, y: int, x: int, s: str, *args: Any) -> None:
        """No-op addstr."""
        return None


def test_draw_single_cell_map(monkeypatch: pytest.MonkeyPatch) -> None:
    """_draw computes _cell_map once per frame."""
    from idle.typing import screen as scr_mod

    orig: Any = scr_mod._cell_map
    calls: list[int] = []

    def _counting(text: str, width: int) -> Any:
        calls.append(1)
        return orig(text, width)

    monkeypatch.setattr(scr_mod, "_cell_map", _counting)
    fake: Any = _FakeCurses()
    state: dict[str, Any] = {"typed": list("hi")}
    scr_mod._draw(fake, "hi there", state, "WPM 10")
    assert len(calls) == 1


def _seed_lc_rows() -> list[dict[str, Any]]:
    """Return 3 rows for cache tests."""
    return [
        {"id": "1", "slug": "two-sum", "title": "Two Sum",
         "difficulty": "Easy", "tags": ["array"]},
        {"id": "2", "slug": "add-two", "title": "Add Two",
         "difficulty": "Medium", "tags": ["linked-list"]},
        {"id": "3", "slug": "hard-p", "title": "Hard P",
         "difficulty": "Hard", "tags": ["dp"]},
    ]


def test_lc_cache_fresh_and_stale(tmp_path: Path) -> None:
    """Fresh rows load, stale row gives None."""
    from idle.lc import api as lc_api

    conn: sqlite3.Connection = get_db(tmp_path / "lc_cache.db")
    try:
        assert lc_api._load_cached_problems(conn) is None
        lc_api._save_problems(conn, _seed_lc_rows())
        fresh: Any = lc_api._load_cached_problems(conn)
        assert fresh is not None
        assert len(fresh) == 3
        assert fresh[0]["slug"] == "two-sum"
        assert "array" in fresh[0]["tags"]
        conn.execute(
            "UPDATE lc_problems SET cached_at='2000-01-01T00:00:00+00:00';"
        )
        conn.commit()
        assert lc_api._load_cached_problems(conn) is None
    finally:
        conn.close()


def test_lc_save_single_executemany(tmp_path: Path) -> None:
    """_save_problems upserts 3 rows via one executemany."""
    from idle.lc import api as lc_api

    conn: sqlite3.Connection = get_db(tmp_path / "lc_exec.db")
    try:
        calls: list[int] = []
        orig: Any = conn.executemany

        def _counting(sql: str, seq: Any) -> Any:
            calls.append(1)
            return orig(sql, seq)

        import unittest.mock as _mock

        with _mock.patch.object(conn, "executemany", _counting):
            lc_api._save_problems(conn, _seed_lc_rows())
        assert len(calls) == 1
        row = conn.execute("SELECT COUNT(*) FROM lc_problems;").fetchone()
        assert int(row[0]) == 3
    finally:
        conn.close()


def test_header_ttl_single_open(tmp_path: Path) -> None:
    """Menu header within TTL opens DB once."""
    from idle import db as db_mod

    db_file: Path = tmp_path / "gui_hdr.db"
    conn: sqlite3.Connection = get_db(db_file)
    try:
        save_typing_session(
            conn, mode="time", duration_s=60.0, net_wpm=70.0,
            raw_wpm=75.0, accuracy=0.9, consistency=0.9,
            text_len=100, per_key={}, per_bigram={},
        )
        conn.execute(
            "INSERT INTO lc_progress(problem_id, status)"
            " VALUES(1, 'solved');"
        )
        conn.commit()
    finally:
        conn.close()
    db_mod.clear_header_cache()
    opens: list[int] = []
    orig: Any = db_mod.get_db

    def _counting(path: Path) -> Any:
        opens.append(1)
        return orig(path)

    import unittest.mock as _mock

    with _mock.patch.object(db_mod, "get_db", _counting):
        first: str = gui_app._menu_header(str(db_file))
        second: str = gui_app._menu_header(str(db_file))
    assert first == second
    assert len(opens) == 1
    assert "70.0" in first
    assert "Solved: 1" in first
    db_mod.clear_header_cache()


def test_no_leetcode_cli_fallback() -> None:
    """Deleted fallback has no import or attribute."""
    import importlib.util

    assert importlib.util.find_spec("idle.lc.api") is not None
    from idle.lc import api as lc_api

    assert hasattr(lc_api, "leetcode_cli_fallback") is False
    with pytest.raises(ImportError):
        from idle.lc.api import leetcode_cli_fallback  # type: ignore[attr-defined] # noqa: F401


def test_ctrl_c_navigates_to_menu_then_quits() -> None:
    """Ctrl+C in a subscreen returns to menu, and on menu exits."""
    _ensure_pygame()
    rt: gui_app._Runtime = gui_app._new_runtime()
    rt.state.push(Screen.TYPE)
    assert rt.state.screen == Screen.TYPE

    ctrl_c_event: Any = _keydown(pygame.K_c, pygame.KMOD_CTRL)
    quit_flag: bool = gui_app._handle_current(ctrl_c_event, rt)
    assert quit_flag is False
    assert rt.state.screen == Screen.MENU

    quit_flag_2: bool = gui_app._handle_current(ctrl_c_event, rt)
    assert quit_flag_2 is True


def test_menu_shortcut_does_not_leak_textinput() -> None:
    """Pressing 1 to enter typing creates session with 0 typed chars."""
    _ensure_pygame()
    rt: gui_app._Runtime = gui_app._new_runtime()
    assert rt.state.screen == Screen.MENU

    key_1: Any = _keydown(pygame.K_1)
    gui_app._handle_current(key_1, rt)
    assert rt.state.screen == Screen.TYPE
    assert rt.typing is not None
    assert len(rt.typing.typed) == 0


def test_gui_initial_screen_navigation() -> None:
    """_goto opens requested initial screens correctly."""
    _ensure_pygame()
    rt: gui_app._Runtime = gui_app._new_runtime()
    gui_app._goto(rt, Screen.TYPE)
    assert rt.state.screen == Screen.TYPE
    assert rt.typing is not None

    rt_drill: gui_app._Runtime = gui_app._new_runtime()
    gui_app._goto(rt_drill, Screen.DRILL)
    assert rt_drill.state.screen == Screen.DRILL
    assert rt_drill.drill is not None

    rt_stats: gui_app._Runtime = gui_app._new_runtime()
    gui_app._goto(rt_stats, Screen.STATS)
    assert rt_stats.state.screen == Screen.STATS
    assert rt_stats.stats_data is not None


def test_stats_pagination_keys() -> None:
    """Left/Right, A/D, and Tab page typing sessions by 10 entries."""
    _ensure_pygame()
    data: dict[str, Any] = {
        "recent": [("1", "ts", "time", 60.0, 50.0, 0.95)] * 10,
        "total": 25,
        "offset": 0,
        "db_path": "",
    }
    # Page forward with Right
    screens_stats.handle_stats(_keydown(pygame.K_RIGHT), data)
    assert data["offset"] == 10

    # Page forward with 'd'
    screens_stats.handle_stats(_keydown(pygame.K_d), data)
    assert data["offset"] == 20

    # Page backward with Left
    screens_stats.handle_stats(_keydown(pygame.K_LEFT), data)
    assert data["offset"] == 10

    # Page backward with 'a'
    screens_stats.handle_stats(_keydown(pygame.K_a), data)
    assert data["offset"] == 0

    # Underflow clamped at 0
    screens_stats.handle_stats(_keydown(pygame.K_a), data)
    assert data["offset"] == 0

    # Page forward with Tab
    screens_stats.handle_stats(_keydown(pygame.K_TAB), data)
    assert data["offset"] == 10


def test_gui_typing_discard_on_esc_and_ctrl_c(tmp_path: Path) -> None:
    """Esc and Ctrl+C discard typing session without adding to DB history."""
    _ensure_pygame()
    db_file: Path = tmp_path / "test.db"
    conn = get_db(db_file)
    conn.close()

    rt: gui_app._Runtime = gui_app._new_runtime()
    rt.state.db_path = str(db_file)
    gui_app._goto(rt, Screen.TYPE)
    assert rt.typing is not None

    # Type a char
    gui_app._handle_session(_textinput("h"), rt)
    assert len(rt.typing.typed) == 1

    # Press ESC: should discard and return to menu
    esc_event = _keydown(pygame.K_ESCAPE)
    gui_app._handle_session(esc_event, rt)
    assert rt.state.screen == Screen.MENU
    assert rt.typing is None

    # Check DB: no sessions saved
    check_conn = get_db(db_file)
    try:
        count = check_conn.execute("SELECT COUNT(*) FROM typing_sessions;").fetchone()
        assert int(count[0]) == 0
    finally:
        check_conn.close()

    # Enter typing again and complete it
    gui_app._goto(rt, Screen.TYPE)
    assert rt.typing is not None
    # Simulate finished and saved
    rt.typing.finished = True
    rt.typing.total = 10
    rt.typing.correct = 10
    rt.typing.text = "hello"
    rt.typing.typed = ["h", "e", "l", "l", "o"]
    save_conn = get_db(db_file)
    try:
        sid = screens_typing.save_and_refresh(rt.typing, save_conn)
        assert sid is not None
        assert rt.typing.session_id == sid
    finally:
        save_conn.close()

    # Verify session is currently in DB
    check_conn = get_db(db_file)
    try:
        count = check_conn.execute("SELECT COUNT(*) FROM typing_sessions;").fetchone()
        assert int(count[0]) == 1
    finally:
        check_conn.close()

    # Pressing ESC on finished session discards it from DB
    gui_app._handle_session(esc_event, rt)
    assert rt.state.screen == Screen.MENU
    assert rt.typing is None

    # Verify session was deleted from DB
    check_conn = get_db(db_file)
    try:
        count = check_conn.execute("SELECT COUNT(*) FROM typing_sessions;").fetchone()
        assert int(count[0]) == 0
    finally:
        check_conn.close()
