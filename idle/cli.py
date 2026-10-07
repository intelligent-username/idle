"""Argparse tree and dispatch with lazy heavy imports."""

from __future__ import annotations

import argparse
from typing import Any


def _add_type_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser], parent: argparse.ArgumentParser | None = None) -> None:
    parents = [parent] if parent else []
    p_type = sub.add_parser("type", aliases=["typing"], parents=parents, help="typing practice")
    mode = p_type.add_mutually_exclusive_group()
    mode.add_argument("--time", type=int, choices=[30, 60, 120], default=None)
    mode.add_argument("--words", type=int, choices=[25, 50, 100], default=None)
    mode.add_argument("--quote", action="store_true")
    mode.add_argument("--code", type=str, choices=["python"], default=None)
    p_type.add_argument("--list", dest="word_list", type=int, choices=[200, 1000], default=200)
    p_type.add_argument("--punct", action="store_true")
    p_type.add_argument("--numbers", action="store_true")
    p_type.add_argument("--stop-on-error", dest="stop_on_error", action="store_true")


def _add_cw_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser], parent: argparse.ArgumentParser | None = None) -> None:
    parents = [parent] if parent else []
    p_cw = sub.add_parser("cw", aliases=["codewars", "lc", "leetcode"], parents=parents, help="codewars practice")
    cw_sub = p_cw.add_subparsers(dest="cw_command")
    cw_sub.add_parser("login", help="configure codewars API token / user")
    p_list = cw_sub.add_parser("list", help="list katas")
    p_list.add_argument("--rank", type=str, default=None, help="filter by rank (e.g. 8 kyu, 6 kyu)")
    p_list.add_argument("--difficulty", type=str, default=None, help="alias for --rank")
    p_list.add_argument("--tag", action="append", default=[])
    p_list.add_argument("--status", type=str, choices=["todo", "solved"], default=None)
    p_list.add_argument("-n", dest="limit", type=int, default=20)
    p_list.add_argument("--refresh", action="store_true")
    p_show = cw_sub.add_parser("show", help="show kata description")
    p_show.add_argument("id_or_slug", type=str)
    p_pick = cw_sub.add_parser("pick", help="pick random unsolved kata")
    p_pick.add_argument("--rank", type=str, default=None)
    p_pick.add_argument("--difficulty", type=str, default=None)
    p_pick.add_argument("--tag", action="append", default=[])
    cw_sub.add_parser("daily", help="daily kata")
    p_start = cw_sub.add_parser("start", help="scaffold solution")
    p_start.add_argument("id_or_slug", type=str)
    p_test = cw_sub.add_parser("test", help="test solution locally")
    p_test.add_argument("id_or_slug", type=str, nargs="?")
    p_submit = cw_sub.add_parser("submit", help="submit solution or open submit page")
    p_submit.add_argument("id_or_slug", type=str, nargs="?")
    cw_sub.add_parser("stats", help="codewars user stats")
    p_open = cw_sub.add_parser("open", help="open in browser")
    p_open.add_argument("id_or_slug", type=str)


def _add_lc_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser], parent: argparse.ArgumentParser | None = None) -> None:
    _add_cw_parser(sub, parent)


def _add_stats_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser], parent: argparse.ArgumentParser | None = None) -> None:
    parents = [parent] if parent else []
    p_stats = sub.add_parser("stats", parents=parents, help="show typing history")
    p_stats.add_argument("--limit", type=int, default=20)


def _add_gui_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser], parent: argparse.ArgumentParser | None = None) -> None:
    """Add gui subcommand for default launch."""
    parents = [parent] if parent else []
    sub.add_parser("gui", parents=parents, help="launch pygame GUI (default)")


def _add_config_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser], parent: argparse.ArgumentParser | None = None) -> None:
    parents = [parent] if parent else []
    p_config = sub.add_parser("config", parents=parents, help="show config")
    p_config.add_argument("--edit", action="store_true")


class IdleParser(argparse.ArgumentParser):
    """Custom parser preserving GUI flag on subcommands."""

    def parse_args(self, args: Any = None, namespace: Any = None) -> argparse.Namespace:
        raw_args: list[str] = list(args) if args is not None else []
        res = super().parse_args(args, namespace)
        if "--gui" in raw_args:
            res.gui = True
        elif not hasattr(res, "gui"):
            res.gui = False
        if hasattr(res, "cw_command") and not hasattr(res, "lc_command"):
            res.lc_command = res.cw_command
        return res


def build_parser() -> argparse.ArgumentParser:
    """Build exact CLI tree for idle."""
    gui_parent = argparse.ArgumentParser(add_help=False)
    gui_parent.add_argument("--gui", action="store_true", help="run in GUI mode and open screen directly")

    parser = IdleParser(
        prog="idle",
        description="Terminal typing + LeetCode toolkit",
        parents=[gui_parent],
    )
    parser.add_argument("--cli", action="store_true", help="use terminal menu instead of GUI")
    sub = parser.add_subparsers(dest="command")
    _add_type_parser(sub, gui_parent)
    sub.add_parser("drill", parents=[gui_parent], help="adaptive drill")
    _add_lc_parser(sub, gui_parent)
    _add_stats_parser(sub, gui_parent)
    _add_config_parser(sub, gui_parent)
    _add_gui_parser(sub, gui_parent)
    return parser


def cmd_config(edit: bool = False) -> None:
    """Print config path and TOML, optionally open editor."""
    from idle.config import load_config
    from idle.config import resolve_paths

    _, config_path, _ = resolve_paths()
    config = load_config()
    print(f"config: {config_path}")
    print(config_path.read_text(encoding="utf-8"), end="")
    if edit:
        _open_editor(config_path, config)


def _open_editor(config_path: object, config: object) -> None:
    import os
    import subprocess

    cfg = config if isinstance(config, dict) else {}
    lc = cfg.get("lc", {}) if isinstance(cfg, dict) else {}
    editor: str = ""
    if isinstance(lc, dict):
        raw = lc.get("editor", "")
        editor = str(raw) if raw else ""
    editor = editor or os.environ.get("EDITOR", "")
    if not editor:
        editor = "notepad" if os.name == "nt" else "vi"
    try:
        subprocess.run([editor, str(config_path)])
    except OSError:
        print(f"could not open editor: {editor}")


def _recent_rows(conn: Any, limit: int) -> list[Any]:
    """Fetch last N typing sessions newest first, excluding drills."""
    cur = conn.execute(
        "SELECT id, ts, mode, duration_s, net_wpm, accuracy"
        " FROM typing_sessions WHERE mode != 'drill'"
        " ORDER BY id DESC LIMIT ?;",
        (max(limit, 0),),
    )
    return list(cur.fetchall())


def _print_rows(rows: list[Any]) -> None:
    """Print plain table of session rows."""
    print(f"{'id':>5}  {'ts':<19}  {'mode':<6}  {'secs':>5}  {'net':>6}  {'acc':>6}")
    for row in rows:
        sid, ts, mode, secs, net, acc = row[0], row[1], row[2], row[3], row[4], row[5]
        short_ts = str(ts)[:19].replace("T", " ")
        print(f"{int(sid):>5}  {short_ts:<19}  {str(mode):<6}  {float(secs):>5.0f}  {float(net):>6.1f}  {float(acc) * 100.0:>5.1f}%")


def _print_agg(conn: Any) -> None:
    """Print Best and 7-day aggregates."""
    from idle.db import get_7day_avg
    from idle.db import get_best

    best: float | None = get_best(conn)
    avg: float | None = get_7day_avg(conn)
    if best is None:
        print("Best: --")
    else:
        print(f"Best: {best:.1f} WPM")
    if avg is None:
        print("7-day: --")
    else:
        print(f"7-day: {avg:.1f} WPM")


def cmd_stats(limit: int = 20) -> None:
    """Show recent typing history as plain table."""
    from idle.config import resolve_paths
    from idle.db import get_db

    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        rows: list[Any] = _recent_rows(conn, limit)
        if not rows:
            print("no sessions yet. Run: idle type")
            return
        _print_rows(rows)
        _print_agg(conn)
    finally:
        conn.close()


def _cfg_typing() -> dict[str, Any]:
    """Load typing config section with safe fallback."""
    from idle.config import load_config

    try:
        cfg: dict[str, Any] = load_config()
    except OSError:
        return {}
    sec: Any = cfg.get("typing", {})
    return dict(sec) if isinstance(sec, dict) else {}


def _resolve_mode(args: argparse.Namespace, cfg: dict[str, Any]) -> tuple[str, float, int, str]:
    """Resolve mode, duration, word count, language."""
    if getattr(args, "time", None) is not None:
        return ("time", float(getattr(args, "time")), 0, "python")
    if getattr(args, "words", None) is not None:
        return ("words", 0.0, int(getattr(args, "words")), "python")
    if getattr(args, "quote", False):
        return ("quote", 0.0, 0, "python")
    if getattr(args, "code", None) is not None:
        return ("code", 0.0, 0, str(getattr(args, "code")))
    mode: str = str(cfg.get("default_mode", "time"))
    if mode == "words":
        return (mode, 0.0, int(cfg.get("default_words", 50)), "python")
    if mode in ("quote", "code"):
        return (mode, 0.0, 0, "python")
    return ("time", float(cfg.get("default_time", 60)), 0, "python")


def _resolve_flags(args: argparse.Namespace, cfg: dict[str, Any]) -> tuple[int, bool, bool, bool]:
    """Resolve word list, punct, numbers, stop flags."""
    import sys

    if "--list" in sys.argv:
        word_list: int = int(getattr(args, "word_list", 200))
    else:
        word_list = int(cfg.get("word_list", getattr(args, "word_list", 200)))
    if word_list not in (200, 1000):
        word_list = 200
    punct: bool = bool(getattr(args, "punct", False) or cfg.get("punct", False))
    numbers: bool = bool(getattr(args, "numbers", False) or cfg.get("numbers", False))
    stop: bool = bool(getattr(args, "stop_on_error", False) or cfg.get("stop_on_error", False))
    return (word_list, punct, numbers, stop)


def _time_word_count(duration: float) -> int:
    """Pick enough words to fill a timed session."""
    if duration <= 30:
        return 120
    if duration <= 60:
        return 240
    return 480


def _make_text(mode: str, word_list: int, num_words: int, punct: bool, numbers: bool) -> str | None:
    """Build test text, None with message on failure."""
    from idle.typing import texts

    try:
        if mode in ("time", "words"):
            words: list[str] = texts.load_words(word_list)
            return texts.make_text(mode, words=words, word_list=word_list, num_words=num_words, punct=punct, numbers=numbers)
        if mode == "quote":
            return texts.make_text("quote")
        if mode == "code":
            return texts.make_text("code", language="python")
    except (OSError, ValueError):
        print("could not build text (data missing?). Reinstall and retry.")
        return None
    print(f"unknown mode: {mode}")
    return None


def _run_curses_text(text: str, opts: dict[str, Any]) -> dict[str, Any] | None:
    """Run curses test, None with message on small screen or cancel."""
    try:
        import curses
    except ImportError:
        print("curses unavailable. On Windows run: pip install windows-curses")
        return None
    from idle.typing import screen as scr

    try:
        result: dict[str, Any] = curses.wrapper(scr.run_typing_test, text, opts)
    except KeyboardInterrupt:
        print("\nexited cleanly")
        return None
    except Exception:
        print("terminal error. Resize and retry.")
        return None
    if isinstance(result, dict) and result.get("error"):
        print("terminal too small (need 40x10). Resize and retry.")
        return None
    return result


def _persist_type_result(conn: Any, mode: str, text: str, result: dict[str, Any]) -> None:
    """Save session on open conn and print formatted results."""
    from idle.db import get_7day_avg
    from idle.db import get_best
    from idle.db import save_typing_session
    from idle.typing.screen import format_results

    total: int = int(result.get("total", 0))
    if total <= 0:
        print("no input recorded")
        return
    save_typing_session(conn, mode=mode, duration_s=float(result.get("elapsed_s", 0.0)), net_wpm=float(result.get("net_wpm", 0.0)), raw_wpm=float(result.get("raw_wpm", 0.0)), accuracy=float(result.get("accuracy", 0.0)), consistency=float(result.get("consistency", 0.0)), text_len=len(text), per_key=dict(result.get("per_key", {})), per_bigram=dict(result.get("per_bigram", {})))
    best: float | None = get_best(conn)
    avg: float | None = get_7day_avg(conn)
    print("\n".join(format_results(result, best, avg)))


def _save_type_result(mode: str, text: str, result: dict[str, Any]) -> None:
    """Persist session and print results with Best and 7-day."""
    from idle.config import resolve_paths
    from idle.db import get_db

    total: int = int(result.get("total", 0))
    if total <= 0:
        print("no input recorded")
        return
    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        _persist_type_result(conn, mode, text, result)
    finally:
        conn.close()


def _cmd_type(args: argparse.Namespace) -> None:
    """Run typing test from CLI flags plus config defaults."""
    cfg: dict[str, Any] = _cfg_typing()
    mode, duration, count, _lang = _resolve_mode(args, cfg)
    word_list, punct, numbers, stop = _resolve_flags(args, cfg)
    if mode == "time":
        num_words: int = _time_word_count(duration)
    elif mode == "words":
        num_words = count if count > 0 else int(cfg.get("default_words", 50))
    else:
        num_words = 0
    text: str | None = _make_text(mode, word_list, num_words, punct, numbers)
    if text is None:
        return
    opts: dict[str, Any] = {"mode": mode, "time": duration, "duration_s": duration, "stop_on_error": stop}
    result: dict[str, Any] | None = _run_curses_text(text, opts)
    if result is None or result.get("quit"):
        return
    _save_type_result(mode, text, result)


def _weak_avg(conn: Any) -> float | None:
    """Average top-K weak scores, None when no data."""
    from idle.typing.drill import weak_avg

    return weak_avg(conn)


def _drill_words(word_list: int) -> list[str] | None:
    """Load drill word source, None with message on failure."""
    from idle.typing.texts import load_words

    try:
        return load_words(word_list)
    except (OSError, ValueError):
        print("could not load drill words (data missing?). Reinstall and retry.")
        return None


def _print_drill_delta(before: float | None, after: float | None) -> None:
    """Print weak score improvement or regression."""
    if before is None or after is None or before <= 0:
        print("drill baseline saved")
        return
    pct: float = (before - after) / before * 100.0
    if after < before:
        print(f"weak score improved by {pct:.1f}%")
    elif after > before:
        print(f"weak score regressed by {-pct:.1f}%")
    else:
        print("weak score unchanged")


def _drill_text_and_before(conn: Any, word_list: int) -> tuple[str | None, float | None]:
    """Score before and build 30-word drill text."""
    from idle.typing.drill import generate_drill_text

    before: float | None = _weak_avg(conn)
    words: list[str] | None = _drill_words(word_list)
    if words is None:
        return (None, before)
    return (generate_drill_text(conn, words, 30), before)


def _cmd_drill() -> None:
    """Run short adaptive drill and show weak score delta."""
    from idle.config import resolve_paths
    from idle.db import get_db

    cfg: dict[str, Any] = _cfg_typing()
    word_list: int = int(cfg.get("word_list", 200))
    if word_list not in (200, 1000):
        word_list = 200
    stop: bool = bool(cfg.get("stop_on_error", False))
    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        text, before = _drill_text_and_before(conn, word_list)
        if not text:
            print("could not build drill text")
            return
        result: dict[str, Any] | None = _run_curses_text(text, {"mode": "drill", "stop_on_error": stop})
        if result is None or result.get("quit"):
            return
        _persist_type_result(conn, "drill", text, result)
        after: float | None = _weak_avg(conn)
    finally:
        conn.close()
    _print_drill_delta(before, after)


def _dispatch_cw(name: str, args: argparse.Namespace) -> None:
    """Route one cw/lc subcommand to its handler."""
    from idle.cw import commands as cw

    if name == "login":
        cw.cmd_login()
    elif name == "list":
        rank = getattr(args, "rank", None) or getattr(args, "difficulty", None)
        cw.cmd_list(rank=rank, tag=getattr(args, "tag", None), status=getattr(args, "status", None), limit=int(getattr(args, "limit", 20)), refresh=bool(getattr(args, "refresh", False)))
    elif name == "show":
        cw.cmd_show(str(getattr(args, "id_or_slug", "")))
    elif name == "pick":
        rank = getattr(args, "rank", None) or getattr(args, "difficulty", None)
        cw.cmd_pick(rank=rank, tag=getattr(args, "tag", None))
    elif name == "daily":
        cw.cmd_daily()
    elif name == "start":
        cw.cmd_start(str(getattr(args, "id_or_slug", "")))
    elif name == "test":
        cw.cmd_test(getattr(args, "id_or_slug", None))
    elif name == "submit":
        cw.cmd_submit(getattr(args, "id_or_slug", None))
    elif name == "stats":
        cw.cmd_cw_stats()
    elif name == "open":
        cw.cmd_open(str(getattr(args, "id_or_slug", "")))
    else:
        print("usage: idle cw {login,list,show,pick,daily,start,test,submit,stats,open}")


def _cmd_cw(args: argparse.Namespace) -> None:
    """Dispatch cw/lc subcommands to cw.commands."""
    name: str | None = getattr(args, "cw_command", None) or getattr(args, "lc_command", None)
    if name is None:
        print("usage: idle cw {login,list,show,pick,daily,start,test,submit,stats,open}")
        return
    try:
        _dispatch_cw(name, args)
    except KeyboardInterrupt:
        print("\nexited cleanly")
    except (OSError, RuntimeError) as exc:
        msg = str(exc).strip()
        if msg:
            print(msg)
        else:
            print("could not complete command (offline?). Check network and retry.")


def _dispatch_lc(name: str, args: argparse.Namespace) -> None:
    _dispatch_cw(name, args)


def _cmd_lc(args: argparse.Namespace) -> None:
    name: str | None = getattr(args, "lc_command", None) or getattr(args, "cw_command", None)
    if name is None:
        print("usage: idle lc {login,list,show,pick,daily,start,test,submit,stats,open}")
        return
    try:
        _dispatch_lc(name, args)
    except KeyboardInterrupt:
        print("\nexited cleanly")
    except (OSError, RuntimeError) as exc:
        msg = str(exc).strip()
        known_msgs = [
            "login failed: HTTP 403 from LeetCode (retry later).",
            "LeetCode challenge detected (captcha/cloudflare). Retry later.",
            "login failed: bad credentials or captcha",
            "Session expired. Run: idle lc login",
            "saved login (unverified, offline?)",
            "login cancelled: empty session",
        ]
        if any(km in msg for km in known_msgs):
            print(msg)
        else:
            print("could not complete lc command (offline?). Check network and retry.")


def _menu_header() -> None:
    """Print Best WPM and solved count one-liners."""
    from idle.config import resolve_paths
    from idle.db import get_db
    from idle.db import get_header_stats

    try:
        conn = get_db(resolve_paths()[0])
        try:
            best: float | None
            solved: int
            best, solved = get_header_stats(conn)
        finally:
            conn.close()
    except OSError:
        print("Best: -- | Solved: 0")
        return
    best_text: str = f"{best:.1f} WPM" if best is not None else "--"
    print(f"Best: {best_text} | Solved: {solved}")


def _menu_type() -> None:
    """Run bare-menu typing with config defaults."""
    args: argparse.Namespace = argparse.Namespace(time=None, words=None, quote=False, code=None, word_list=200, punct=False, numbers=False, stop_on_error=False)
    _cmd_type(args)


def run_menu() -> None:
    """Show numbered menu loop using plain input."""
    while True:
        _menu_header()
        print("1) type  2) drill  3) leetcode  4) stats  5) quit")
        try:
            choice: str = input("select: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nexited cleanly")
            return
        if choice in ("5", "q", "quit", "exit"):
            return
        if choice in ("1", "type"):
            _menu_type()
        elif choice in ("2", "drill"):
            _cmd_drill()
        elif choice in ("3", "leetcode", "lc"):
            print("usage: idle lc {login,list,show,pick,daily,start,test,submit,stats,open}")
        elif choice in ("4", "stats"):
            cmd_stats()
        else:
            print("pick 1-5")


def main(argv: list[str] | None = None) -> int:
    """Parse args and dispatch, restoring terminal on Ctrl+C."""
    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args(argv)
    try:
        if bool(getattr(args, "gui", False)) and args.command not in (None, "gui"):
            try:
                import pygame
            except ImportError:
                print("pygame missing. Run: uv sync")
                return 2
            from idle.gui.app import run_gui
            return run_gui(argv, initial_screen=args.command)
        if bool(getattr(args, "cli", False)) and args.command in (None, "gui"):
            run_menu()
            return 0
        if args.command is None or args.command == "gui":
            try:
                import pygame
            except ImportError:
                print("pygame missing. Run: uv sync")
                return 2
            from idle.gui.app import run_gui
            return run_gui(argv)
        elif args.command in ("type", "typing"):
            _cmd_type(args)
        elif args.command == "drill":
            _cmd_drill()
        elif args.command in ("cw", "codewars", "lc", "leetcode"):
            _cmd_cw(args)
        elif args.command == "stats":
            cmd_stats(getattr(args, "limit", 20))
        elif args.command == "config":
            cmd_config(getattr(args, "edit", False))
    except KeyboardInterrupt:
        print("\nexited cleanly")
    return 0
