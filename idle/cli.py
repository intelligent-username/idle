"""Argparse tree and dispatch with lazy heavy imports."""

import argparse
from typing import Any


def _add_type_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p_type = sub.add_parser("type", help="typing practice")
    mode = p_type.add_mutually_exclusive_group()
    mode.add_argument("--time", type=int, choices=[30, 60, 120], default=None)
    mode.add_argument("--words", type=int, choices=[25, 50, 100], default=None)
    mode.add_argument("--quote", action="store_true")
    mode.add_argument("--code", type=str, choices=["python"], default=None)
    p_type.add_argument("--list", dest="word_list", type=int, choices=[200, 1000], default=200)
    p_type.add_argument("--punct", action="store_true")
    p_type.add_argument("--numbers", action="store_true")
    p_type.add_argument("--stop-on-error", dest="stop_on_error", action="store_true")


def _add_lc_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p_lc = sub.add_parser("lc", help="leetcode practice")
    lc_sub = p_lc.add_subparsers(dest="lc_command")
    lc_sub.add_parser("login", help="login with browser cookies")
    p_list = lc_sub.add_parser("list", help="list problems")
    p_list.add_argument("--difficulty", type=str, choices=["e", "m", "h"], default=None)
    p_list.add_argument("--tag", action="append", default=[])
    p_list.add_argument("--status", type=str, choices=["todo", "solved"], default=None)
    p_list.add_argument("-n", dest="limit", type=int, default=20)
    p_list.add_argument("--refresh", action="store_true")
    p_show = lc_sub.add_parser("show", help="show problem")
    p_show.add_argument("id_or_slug", type=str)
    p_pick = lc_sub.add_parser("pick", help="pick random unsolved")
    p_pick.add_argument("--difficulty", type=str, choices=["e", "m", "h"], default=None)
    p_pick.add_argument("--tag", action="append", default=[])
    lc_sub.add_parser("daily", help="daily challenge")
    p_start = lc_sub.add_parser("start", help="scaffold solution")
    p_start.add_argument("id_or_slug", type=str)
    p_test = lc_sub.add_parser("test", help="test solution remotely")
    p_test.add_argument("id_or_slug", type=str, nargs="?")
    p_submit = lc_sub.add_parser("submit", help="submit solution")
    p_submit.add_argument("id_or_slug", type=str, nargs="?")
    lc_sub.add_parser("stats", help="leetcode stats")
    p_open = lc_sub.add_parser("open", help="open in browser")
    p_open.add_argument("id_or_slug", type=str)


def _add_stats_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p_stats = sub.add_parser("stats", help="show typing history")
    p_stats.add_argument("--limit", type=int, default=20)


def _add_config_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    p_config = sub.add_parser("config", help="show config")
    p_config.add_argument("--edit", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    """Build exact CLI tree for idle."""
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        prog="idle",
        description="Terminal typing + LeetCode toolkit",
    )
    sub = parser.add_subparsers(dest="command")
    _add_type_parser(sub)
    sub.add_parser("drill", help="adaptive drill")
    _add_lc_parser(sub)
    _add_stats_parser(sub)
    _add_config_parser(sub)
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
    """Fetch last N typing sessions newest first."""
    cur = conn.execute(
        "SELECT id, ts, mode, duration_s, net_wpm, accuracy"
        " FROM typing_sessions ORDER BY id DESC LIMIT ?;",
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


def _save_type_result(mode: str, text: str, result: dict[str, Any]) -> None:
    """Persist session and print results with Best and 7-day."""
    from idle.config import resolve_paths
    from idle.db import get_7day_avg
    from idle.db import get_best
    from idle.db import get_db
    from idle.db import save_typing_session
    from idle.typing import screen as scr

    total: int = int(result.get("total", 0))
    if total <= 0:
        print("no input recorded")
        return
    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        save_typing_session(conn, mode=mode, duration_s=float(result.get("elapsed_s", 0.0)), net_wpm=float(result.get("net_wpm", 0.0)), raw_wpm=float(result.get("raw_wpm", 0.0)), accuracy=float(result.get("accuracy", 0.0)), consistency=float(result.get("consistency", 0.0)), text_len=len(text), per_key=dict(result.get("per_key", {})), per_bigram=dict(result.get("per_bigram", {})))
        best: float | None = get_best(conn)
        avg: float | None = get_7day_avg(conn)
    finally:
        conn.close()
    scr.show_results(result, best, avg)


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
    if result is None:
        return
    _save_type_result(mode, text, result)


def _weak_avg(conn: Any) -> float | None:
    """Average top-K weak scores, None when no data."""
    from idle.typing.drill import TOP_K
    from idle.typing.drill import score_keys

    scores: dict[str, float] = score_keys(conn)
    if not scores:
        return None
    top: list[float] = sorted(scores.values(), reverse=True)[:TOP_K]
    if not top:
        return None
    return sum(top) / len(top)


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
    finally:
        conn.close()
    if not text:
        print("could not build drill text")
        return
    result: dict[str, Any] | None = _run_curses_text(text, {"mode": "drill", "stop_on_error": stop})
    if result is None:
        return
    _save_type_result("drill", text, result)
    conn2 = get_db(db_path)
    try:
        after: float | None = _weak_avg(conn2)
    finally:
        conn2.close()
    _print_drill_delta(before, after)


def _dispatch_lc(name: str, args: argparse.Namespace) -> None:
    """Route one lc subcommand to its handler."""
    from idle.lc import commands as lc

    if name == "login":
        lc.cmd_login()
    elif name == "list":
        lc.cmd_list(difficulty=getattr(args, "difficulty", None), tag=getattr(args, "tag", None), status=getattr(args, "status", None), limit=int(getattr(args, "limit", 20)), refresh=bool(getattr(args, "refresh", False)))
    elif name == "show":
        lc.cmd_show(str(getattr(args, "id_or_slug", "")))
    elif name == "pick":
        lc.cmd_pick(difficulty=getattr(args, "difficulty", None), tag=getattr(args, "tag", None))
    elif name == "daily":
        lc.cmd_daily()
    elif name == "start":
        lc.cmd_start(str(getattr(args, "id_or_slug", "")))
    elif name == "test":
        lc.cmd_test(getattr(args, "id_or_slug", None))
    elif name == "submit":
        lc.cmd_submit(getattr(args, "id_or_slug", None))
    elif name == "stats":
        lc.cmd_lc_stats()
    elif name == "open":
        lc.cmd_open(str(getattr(args, "id_or_slug", "")))
    else:
        print("usage: idle lc {login,list,show,pick,daily,start,test,submit,stats,open}")


def _cmd_lc(args: argparse.Namespace) -> None:
    """Dispatch lc subcommands to lc.commands."""
    name: str | None = getattr(args, "lc_command", None)
    if name is None:
        print("usage: idle lc {login,list,show,pick,daily,start,test,submit,stats,open}")
        return
    try:
        _dispatch_lc(name, args)
    except KeyboardInterrupt:
        print("\nexited cleanly")
    except (OSError, RuntimeError):
        print("could not complete lc command (offline?). Check network and retry.")


def _best_text() -> str:
    """Return Best WPM one-liner value."""
    from idle.config import resolve_paths
    from idle.db import get_best
    from idle.db import get_db

    try:
        conn = get_db(resolve_paths()[0])
        try:
            best: float | None = get_best(conn)
        finally:
            conn.close()
    except OSError:
        return "--"
    if best is None:
        return "--"
    return f"{best:.1f} WPM"


def _solved_text() -> str:
    """Return solved count one-liner value."""
    from idle.config import resolve_paths
    from idle.db import get_db

    try:
        conn = get_db(resolve_paths()[0])
        try:
            row = conn.execute("SELECT COUNT(*) FROM lc_progress WHERE status='solved';").fetchone()
        finally:
            conn.close()
    except OSError:
        return "0"
    count: int = int(row[0]) if row else 0
    return str(count)


def _menu_header() -> None:
    """Print Best WPM and solved count one-liners."""
    print(f"Best: {_best_text()} | Solved: {_solved_text()}")


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


def main(argv: list[str] | None = None) -> None:
    """Parse args and dispatch, restoring terminal on Ctrl+C."""
    parser: argparse.ArgumentParser = build_parser()
    args: argparse.Namespace = parser.parse_args(argv)
    try:
        if args.command is None:
            run_menu()
        elif args.command == "type":
            _cmd_type(args)
        elif args.command == "drill":
            _cmd_drill()
        elif args.command == "lc":
            _cmd_lc(args)
        elif args.command == "stats":
            cmd_stats(getattr(args, "limit", 20))
        elif args.command == "config":
            cmd_config(getattr(args, "edit", False))
    except KeyboardInterrupt:
        print("\nexited cleanly")
