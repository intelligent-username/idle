"""Pygame app shell with screen stack and main loop."""

from dataclasses import dataclass
from typing import Any

from idle.gui import theme
from idle.gui.state import AppState, Screen

__all__: list[str] = ["run_gui"]

INSTALL_HINT = "pygame missing. Run: pip install idle[gui]"
TITLE = "idle"
FONT_SIZE = 20


@dataclass
class _Runtime:
    """Mutable views and nav state for the main loop."""

    state: AppState
    menu_selected: int = 0
    menu_header: str = ""
    typing: Any = None
    drill: Any = None
    lc_list: Any = None
    lc_detail: Any = None
    lc_solve: Any = None
    login: Any = None
    show_login: bool = False
    stats_data: Any = None
    config_view: Any = None


def _shell_paths() -> tuple[str, dict[str, Any]]:
    """Return db path and config, empty friendly on error."""
    from idle.config import load_config, resolve_paths

    try:
        db_path, _, _ = resolve_paths()
    except OSError:
        return ("", {})
    try:
        cfg: dict[str, Any] = dict(load_config())
    except OSError:
        cfg = {}
    return (str(db_path), cfg)


def _menu_header(db_path: str) -> str:
    """Return cached Best/Solved header, refresh after TTL."""
    if not db_path:
        return "Best: -- | Solved: 0"
    from idle.db import get_cached_header

    try:
        return get_cached_header(db_path)
    except OSError:
        return "Best: -- | Solved: 0"


def _new_runtime() -> _Runtime:
    """Build runtime with paths, header, and empty LC views."""
    from idle.gui import screens_lc

    db_path, cfg = _shell_paths()
    state = AppState(db_path=db_path, config=cfg)
    return _Runtime(
        state=state,
        menu_header=_menu_header(db_path),
        lc_list=screens_lc.LcListState(),
        lc_detail=screens_lc.LcDetailState(),
        login=screens_lc.make_login_state(),
    )


TYPING_DIFFICULTIES: list[dict[str, Any]] = [
    {
        "name": "Easy",
        "num_words": 25,
        "limit_s": 300.0,
        "punct": False,
        "numbers": False,
        "stop_on_error": False,
    },
    {
        "name": "Medium",
        "num_words": 40,
        "limit_s": 300.0,
        "punct": False,
        "numbers": False,
        "stop_on_error": False,
    },
    {
        "name": "Hard",
        "num_words": 60,
        "limit_s": 300.0,
        "punct": True,
        "numbers": False,
        "stop_on_error": False,
    },
    {
        "name": "Expert",
        "num_words": 75,
        "limit_s": 300.0,
        "punct": True,
        "numbers": True,
        "stop_on_error": False,
    },
    {
        "name": "Master",
        "num_words": 90,
        "limit_s": 300.0,
        "punct": True,
        "numbers": True,
        "stop_on_error": False,
    },
]

DRILL_DIFFICULTIES: list[dict[str, Any]] = [
    {"name": "Easy", "length": 30, "weak_keys": 3, "stop_on_error": False},
    {"name": "Medium", "length": 45, "weak_keys": 5, "stop_on_error": False},
    {"name": "Hard", "length": 60, "weak_keys": 7, "stop_on_error": False},
    {"name": "Expert", "length": 75, "weak_keys": 9, "stop_on_error": False},
    {"name": "Master", "length": 90, "weak_keys": 12, "stop_on_error": False},
]


def _enter_typing(rt: _Runtime) -> None:
    """Start typing session from config and difficulty, friendly on error."""
    from idle.gui import screens_typing

    cfg: Any = rt.state.config.get("typing", {})
    if not isinstance(cfg, dict):
        cfg = {}
    diff_idx: int = (
        getattr(rt.state, "typing_difficulty", 0) % len(TYPING_DIFFICULTIES)
    )
    diff = TYPING_DIFFICULTIES[diff_idx]
    try:
        text: str = screens_typing.build_typing_text(
            mode=str(cfg.get("default_mode", "time")),
            word_list=int(cfg.get("word_list", 200)),
            num_words=int(diff["num_words"]),
            punct=bool(diff["punct"]),
            numbers=bool(diff["numbers"]),
            difficulty=diff_idx,
        )
    except (OSError, RuntimeError, ValueError):
        rt.state.message = "could not load words (offline?)."
        return
    rt.typing = screens_typing.new_typing_session(
        text,
        mode=str(cfg.get("default_mode", "time")),
        stop_on_error=bool(diff["stop_on_error"]),
        limit_s=float(diff["limit_s"]),
        difficulty=str(diff["name"]),
    )
    rt.state.message = ""


def _drill_text(
    db_path: str,
    words: list[str],
    length: int = 30,
    weak_keys: int = 5,
    difficulty: int = 0,
) -> str:
    """Build weak-key drill text using existing DB scores and difficulty."""
    from pathlib import Path

    from idle.db import get_db
    from idle.gui import screens_typing

    conn = get_db(Path(db_path))
    try:
        return screens_typing.build_drill_text(
            conn,
            words,
            length=length,
            weak_keys=weak_keys,
            difficulty=difficulty,
        )
    finally:
        conn.close()


def _enter_drill(rt: _Runtime) -> None:
    """Start drill session, plain words fallback when DB fails."""
    from idle.gui import screens_typing

    cfg: Any = rt.state.config.get("typing", {})
    if not isinstance(cfg, dict):
        cfg = {}
    diff_idx: int = (
        getattr(rt.state, "drill_difficulty", 0) % len(DRILL_DIFFICULTIES)
    )
    diff = DRILL_DIFFICULTIES[diff_idx]
    length: int = int(diff["length"])
    weak_keys: int = int(diff["weak_keys"])
    stop: bool = bool(diff["stop_on_error"])

    try:
        words: list[str] = screens_typing.load_words(
            1000 if diff_idx >= 1 else 200
        )
    except (OSError, RuntimeError, ValueError):
        rt.state.message = "could not load words (offline?)."
        return
    text: str = " ".join(words[:length]) if words else ""
    if rt.state.db_path and words:
        try:
            text = _drill_text(
                rt.state.db_path,
                words,
                length=length,
                weak_keys=weak_keys,
                difficulty=diff_idx,
            )
        except (OSError, RuntimeError, ValueError):
            pass
    if not text:
        rt.state.message = "no drill text available."
        return
    rt.drill = screens_typing.new_drill_session(
        text, stop_on_error=stop, difficulty=str(diff["name"])
    )
    rt.state.message = ""



def _enter_lc_list(rt: _Runtime) -> None:
    """Require login first, auto-logging in if credentials available."""
    from idle.gui import screens_lc

    if rt.lc_list is None:
        rt.lc_list = screens_lc.LcListState()
    if screens_lc.auth_needed():
        ok, msg = screens_lc.try_auto_login()
        if not ok:
            if msg and msg != "no credentials provided":
                rt.login.message = msg
            rt.show_login = True
            return
        rt.state.message = "saved login"
    view: Any = rt.lc_list
    if not view.problems and not view.message:
        screens_lc.refresh_problem_list(view)
    if view.needs_login:
        ok, msg = screens_lc.try_auto_login()
        if ok:
            view.needs_login = False
            screens_lc.refresh_problem_list(view)
        else:
            if msg and msg != "no credentials provided":
                rt.login.message = msg
            rt.show_login = True


def _enter_stats(rt: _Runtime) -> None:
    """Cache stats rows, empty friendly when DB missing."""
    from idle.gui import screens_stats

    if not rt.state.db_path:
        rt.stats_data = screens_stats.load_stats(".", limit=10, offset=0)
        return
    try:
        rt.stats_data = screens_stats.load_stats(rt.state.db_path, limit=10, offset=0)
    except (OSError, RuntimeError, ValueError):
        rt.stats_data = screens_stats.load_stats(".", limit=10, offset=0)


def _enter_config(rt: _Runtime) -> None:
    """Cache read-only config view, defaults on error."""
    from idle.gui import screens_stats

    try:
        rt.config_view = screens_stats.load_config_view()
    except OSError:
        rt.config_view = {"config": {}}


def _goto(rt: _Runtime, screen: Screen) -> None:
    """Push screen and run its enter hook."""
    rt.state.push(screen)
    if screen == Screen.TYPE:
        _enter_typing(rt)
    elif screen == Screen.DRILL:
        _enter_drill(rt)
    elif screen == Screen.LC_LIST:
        _enter_lc_list(rt)
    elif screen == Screen.STATS:
        _enter_stats(rt)
    elif screen == Screen.CONFIG:
        _enter_config(rt)


def _go_back(rt: _Runtime) -> None:
    """Pop stack, refresh menu header when landing on menu."""
    rt.show_login = False
    rt.state.pop()
    if rt.state.screen == Screen.MENU:
        rt.menu_header = _menu_header(rt.state.db_path)


def _discard_session(session: Any, db_path: str) -> None:
    """Discard unfinished/aborted session, deleting from DB if saved before completion."""
    if session is None:
        return
    if getattr(session, "finished", False):
        return
    session_id: int | None = getattr(session, "session_id", None)
    if session_id is not None and db_path:
        from pathlib import Path
        from idle.db import clear_header_cache, delete_typing_session, get_db

        try:
            conn = get_db(Path(db_path))
            try:
                delete_typing_session(conn, session_id)
                clear_header_cache()
            finally:
                conn.close()
        except OSError:
            pass
        session.session_id = None


def _go_menu(rt: _Runtime) -> None:
    """Clear screen stack, reset session state, and return to menu."""
    rt.show_login = False
    _discard_current_session(rt)
    rt.state.stack.clear()
    rt.state.screen = Screen.MENU
    rt.menu_header = _menu_header(rt.state.db_path)


def _open_selected(rt: _Runtime) -> None:
    """Open current random problem in detail view."""
    from idle.gui import screens_lc

    view: Any = rt.lc_list
    current: Any = getattr(view, "current", None)
    if isinstance(current, dict) and current.get("slug"):
        row: dict[str, Any] = current
    else:
        rows: list[dict[str, Any]] = screens_lc.apply_lc_filters(
            view.problems,
            view.filters.difficulty,
            view.filters.tag,
            view.filters.status,
            view.filters.limit,
        )
        idx: int = int(view.items.selected)
        if not 0 <= idx < len(rows):
            view.message = "no problem selected."
            return
        row = rows[idx]
    key: str = str(row.get("slug") or row.get("id") or "")
    detail: Any
    text: str
    message: str
    login: bool
    detail, text, message, login = screens_lc.load_detail(key)
    if login:
        view.message = message
        rt.show_login = True
        return
    if detail is None:
        view.message = message or "could not fetch (offline?)."
        return
    slug: str = str(detail.get("slug", key))
    rt.lc_detail = screens_lc.make_detail_state(detail, text, slug)
    rt.state.push(Screen.LC_DETAIL)


def _open_daily(rt: _Runtime) -> None:
    """Open daily challenge in detail view."""
    from idle.gui import screens_lc

    view: Any = rt.lc_list
    detail: Any
    text: str
    message: str
    login: bool
    detail, text, message, login = screens_lc.load_daily()
    if login:
        view.message = message
        rt.show_login = True
        return
    if detail is None:
        view.message = message or "could not fetch (offline?)."
        return
    slug: str = str(detail.get("slug", "daily"))
    rt.lc_detail = screens_lc.make_detail_state(detail, text, slug)
    rt.state.push(Screen.LC_DETAIL)


def _do_test(rt: _Runtime) -> None:
    """Run sample tests for solve view, friendly on error."""
    from idle.gui import screens_lc

    view: Any = rt.lc_solve
    if view is None:
        return
    result: Any
    panel: str
    login: bool
    result, panel, login = screens_lc.run_test_action(
        view.detail, view.editor.text, view.data_input
    )
    if login:
        view.message = panel
        rt.show_login = True
        return
    if result is None:
        view.message = panel
        return
    view.verdict = result
    view.panel = panel
    view.message = panel.splitlines()[0] if panel else ""


def _do_submit(rt: _Runtime) -> None:
    """Submit solve view, poll verdict, friendly on error."""
    from idle.gui import screens_lc

    view: Any = rt.lc_solve
    if view is None:
        return
    verdict: Any
    panel: str
    login: bool
    solved: bool
    verdict, panel, login, solved = screens_lc.run_submit_action(
        view.detail, view.editor.text
    )
    if login:
        view.message = panel
        rt.show_login = True
        return
    if verdict is None:
        view.message = panel
        return
    view.verdict = verdict
    view.panel = panel
    view.solved = solved
    view.message = panel.splitlines()[0] if panel else ""


def _save_finished(session: Any, db_path: str) -> str:
    """Persist finished typing session, notice or empty."""
    if session is None or not db_path:
        return ""
    from pathlib import Path

    from idle.db import get_db
    from idle.gui import screens_typing

    try:
        conn = get_db(Path(db_path))
    except OSError:
        return "could not save session."
    try:
        screens_typing.save_and_refresh(session, conn)
    except (OSError, RuntimeError, ValueError):
        return "could not save session."
    finally:
        conn.close()
    return ""


def _discard_current_session(rt: _Runtime) -> None:
    """Discard active session, removing from DB if previously saved."""
    is_type: bool = rt.state.screen == Screen.TYPE
    session: Any = rt.typing if is_type else rt.drill
    _discard_session(session, rt.state.db_path)
    if is_type:
        rt.typing = None
    else:
        rt.drill = None


def _draw_notice(surface: Any, font: Any, rt: _Runtime) -> None:
    """Draw fallback message when a session failed to start."""
    surface.fill(theme.BG)
    msg: str = rt.state.message or "could not start session."
    img: Any = font.render(msg, True, theme.FG)
    surface.blit(img, (32, 64))


def _draw_current(surface: Any, font: Any, rt: _Runtime) -> None:
    """Dispatch draw to active screen, login overlay first."""
    from idle.gui import screens_lc, screens_menu, screens_stats, screens_typing

    if rt.show_login:
        screens_lc.draw_lc_login(surface, font, rt.login)
        return
    screen: Screen = rt.state.screen
    if screen == Screen.MENU:
        screens_menu.draw_menu(surface, rt.state, rt.menu_selected, rt.menu_header)
    elif screen == Screen.TYPE:
        if rt.typing is None:
            _enter_typing(rt)
        if rt.typing is None:
            _draw_notice(surface, font, rt)
        else:
            screens_typing.draw_typing(surface, rt.state, rt.typing)
    elif screen == Screen.DRILL:
        if rt.drill is None:
            _enter_drill(rt)
        if rt.drill is None:
            _draw_notice(surface, font, rt)
        else:
            screens_typing.draw_drill(surface, rt.state, rt.drill)
    elif screen == Screen.LC_LIST:
        screens_lc.draw_lc_list(surface, font, rt.lc_list)
    elif screen == Screen.LC_DETAIL:
        screens_lc.draw_lc_detail(surface, font, rt.lc_detail)
    elif screen == Screen.LC_SOLVE:
        screens_lc.draw_lc_solve(surface, font, rt.lc_solve)
    elif screen == Screen.STATS:
        screens_stats.draw_stats(surface, rt.state, rt.stats_data)
    elif screen == Screen.CONFIG:
        screens_stats.draw_config(surface, rt.state, rt.config_view)


def _handle_menu(event: Any, rt: _Runtime) -> bool:
    """Handle menu nav. Return True to quit."""
    from idle.gui import screens_menu

    selected: int
    target: Any
    quit: bool
    selected, target, quit = screens_menu.handle_menu(
        event, rt.menu_selected, rt.state
    )
    rt.menu_selected = selected
    if quit:
        return True
    if target is not None:
        _goto(rt, target)
    return False


def _handle_session(event: Any, rt: _Runtime) -> bool:
    """Handle typing and drill keys, save on finish. Never quits."""
    from idle.gui import screens_typing

    is_type: bool = rt.state.screen == Screen.TYPE
    if is_type and rt.typing is None:
        _enter_typing(rt)
    if not is_type and rt.drill is None:
        _enter_drill(rt)
    session: Any = rt.typing if is_type else rt.drill
    if session is None:
        return False
    if is_type:
        action: Any = screens_typing.handle_typing(event, session)
    else:
        action = screens_typing.handle_drill(event, session)
    if action == "back":
        _discard_current_session(rt)
        _go_back(rt)
    elif action == "restart":
        _discard_current_session(rt)
        if is_type:
            _enter_typing(rt)
        else:
            _enter_drill(rt)
    elif action == "finished":
        rt.state.message = _save_finished(session, rt.state.db_path)
    return False


def _handle_list(event: Any, rt: _Runtime) -> None:
    """Handle LC random nav, filters, refresh, open, daily."""
    from idle.gui import screens_lc

    action: Any = screens_lc.handle_lc_list(event, rt.lc_list)
    if action == "back":
        _go_back(rt)
    elif action == "random":
        screens_lc.repick_random(rt.lc_list)
    elif action == "refresh":
        screens_lc.refresh_problem_list(rt.lc_list, refresh=True)
        if rt.lc_list.needs_login:
            rt.show_login = True
    elif action == "open":
        _open_selected(rt)
    elif action == "daily":
        _open_daily(rt)


def _handle_detail(event: Any, rt: _Runtime) -> None:
    """Handle detail scroll, solve, open, back."""
    from idle.gui import screens_lc

    action: Any = screens_lc.handle_lc_detail(event, rt.lc_detail)
    if action == "back":
        _go_back(rt)
    elif action == "solve":
        detail: Any = rt.lc_detail.detail or {}
        rt.lc_solve = screens_lc.make_solve_state(detail)
        rt.state.push(Screen.LC_SOLVE)
    elif action == "open":
        rt.lc_detail.message = screens_lc.open_problem(rt.lc_detail.slug)


def _handle_solve(event: Any, rt: _Runtime) -> None:
    """Handle editor keys plus test, submit, open, back."""
    from idle.gui import screens_lc

    action: Any = screens_lc.handle_lc_solve(event, rt.lc_solve)
    if action == "back":
        _go_back(rt)
    elif action == "test":
        _do_test(rt)
    elif action == "submit":
        _do_submit(rt)
    elif action == "open":
        rt.lc_solve.message = screens_lc.open_problem(rt.lc_solve.slug)


def _handle_lc(event: Any, rt: _Runtime) -> bool:
    """Route event to LC list, detail, or solve. Never quits."""
    screen: Screen = rt.state.screen
    if screen == Screen.LC_LIST:
        _handle_list(event, rt)
    elif screen == Screen.LC_DETAIL:
        _handle_detail(event, rt)
    elif screen == Screen.LC_SOLVE:
        _handle_solve(event, rt)
    return False


def _handle_info(event: Any, rt: _Runtime) -> bool:
    """Handle stats and config Esc back. Never quits."""
    from idle.gui import screens_stats

    if rt.state.screen == Screen.STATS:
        if screens_stats.handle_stats(event, rt.stats_data, rt.state.db_path):
            _go_back(rt)
    elif rt.state.screen == Screen.CONFIG:
        if screens_stats.handle_config(event):
            _go_back(rt)
    return False


def _handle_login(event: Any, rt: _Runtime) -> bool:
    """Handle username login, lazy-load random on success."""
    from idle.gui import screens_lc
    from idle.gui.widgets import Textbox
    from idle.lc.auth import load_saved_credentials

    if not rt.login.username_box.text and not rt.login.password_box.text:
        user, pw = load_saved_credentials()
        if user:
            rt.login.username_box = Textbox(text=user)
        if pw:
            rt.login.password_box = Textbox(text=pw)

    action: Any = screens_lc.handle_lc_login(event, rt.login)
    if action == "back":
        rt.show_login = False
    elif action == "login_ok":
        rt.show_login = False
        rt.state.message = "saved login"
        try:
            if rt.lc_list is not None and not rt.lc_list.problems:
                screens_lc.refresh_problem_list(rt.lc_list)
                if rt.lc_list.needs_login:
                    rt.show_login = True
        except (OSError, RuntimeError):
            pass
    return False


def _handle_current(event: Any, rt: _Runtime) -> bool:
    """Route event to active screen. Return True to quit."""
    import pygame

    if rt.show_login:
        return _handle_login(event, rt)
    if rt.state.screen == Screen.LC_SOLVE:
        return _handle_lc(event, rt)
    if int(getattr(event, "type", -1)) == pygame.KEYDOWN:
        key: int = int(getattr(event, "key", 0))
        mod: int = int(getattr(event, "mod", 0))
        if key == pygame.K_c and bool(mod & pygame.KMOD_CTRL):
            if rt.state.screen != Screen.MENU:
                _go_menu(rt)
                return False
            return True
    screen: Screen = rt.state.screen
    if screen == Screen.MENU:
        return _handle_menu(event, rt)
    if screen in (Screen.TYPE, Screen.DRILL):
        return _handle_session(event, rt)
    if screen in (Screen.LC_LIST, Screen.LC_DETAIL):
        return _handle_lc(event, rt)
    return _handle_info(event, rt)


def run_gui(
    argv: list[str] | None = None,
    initial_screen: Screen | str | None = None,
) -> int:
    """Open 960x640 window and run screen stack loop.

    Test: with dummy video and QUIT event, returns 0.
    """
    _ = argv
    try:
        import pygame
    except ImportError:
        print(INSTALL_HINT)
        return 2
    pygame.init()
    size: tuple[int, int] = (theme.LOGICAL_W, theme.LOGICAL_H)
    surface: Any = pygame.display.set_mode(size, pygame.RESIZABLE)
    pygame.display.set_caption(TITLE)
    clock: Any = pygame.time.Clock()
    font: Any = theme.get_font(FONT_SIZE)
    rt: _Runtime = _new_runtime()
    if isinstance(initial_screen, str):
        mapping: dict[str, Screen] = {
            "type": Screen.TYPE,
            "typing": Screen.TYPE,
            "drill": Screen.DRILL,
            "lc": Screen.LC_LIST,
            "leetcode": Screen.LC_LIST,
            "stats": Screen.STATS,
            "config": Screen.CONFIG,
            "menu": Screen.MENU,
            "gui": Screen.MENU,
        }
        initial_screen = mapping.get(initial_screen.lower())
    if initial_screen is not None and initial_screen != Screen.MENU:
        _goto(rt, initial_screen)
    running: bool = True
    try:
        while running:
            for event in pygame.event.get():
                etype: int = int(getattr(event, "type", -1))
                if etype == pygame.QUIT:
                    running = False
                    break
                if etype == pygame.VIDEORESIZE:
                    w: int = int(getattr(event, "w", theme.LOGICAL_W))
                    h: int = int(getattr(event, "h", theme.LOGICAL_H))
                    surface = pygame.display.set_mode((w, h), pygame.RESIZABLE)
                if etype in (
                    getattr(pygame, "WINDOWFOCUSGAINED", 32784),
                    getattr(pygame, "ACTIVEEVENT", 1),
                    pygame.MOUSEBUTTONDOWN,
                ):
                    try:
                        pygame.key.start_text_input()
                    except Exception:
                        pass
                elif etype in (pygame.KEYDOWN, pygame.TEXTINPUT, getattr(pygame, "MOUSEWHEEL", 1027)):
                    screen_before = (rt.state.screen, rt.show_login)
                    if _handle_current(event, rt):
                        running = False
                        break
                    if (rt.state.screen, rt.show_login) != screen_before:
                        try:
                            pygame.event.clear(pygame.TEXTINPUT)
                        except Exception:
                            pass
                        break
            _draw_current(surface, font, rt)
            pygame.display.flip()
            clock.tick(theme.FPS)
    except (KeyboardInterrupt, SystemExit):
        return 0
    finally:
        pygame.quit()
    return 0
