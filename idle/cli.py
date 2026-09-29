"""Argparse tree and dispatch with lazy heavy imports."""

import argparse


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


def cmd_stats(limit: int = 20) -> None:
    """Show recent typing history placeholder for slice 1."""
    from idle.config import resolve_paths
    from idle.db import get_db

    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        rows = conn.execute(
            "SELECT COUNT(*) FROM typing_sessions;"
        ).fetchone()
        count: int = int(rows[0]) if rows else 0
        if count == 0:
            print("no sessions yet")
        else:
            print(f"sessions: {count} (last {limit})")
    finally:
        conn.close()


def _cmd_type(args: argparse.Namespace) -> None:
    print("typing test coming in slice 02")


def _cmd_drill() -> None:
    print("drill coming in slice 04")


def _cmd_lc(args: argparse.Namespace) -> None:
    name: str | None = getattr(args, "lc_command", None)
    if name is None:
        print("usage: idle lc {login,list,show,pick,daily,start,test,submit,stats,open}")
        return
    print(f"lc {name} coming in slice 05-06")


def run_menu() -> None:
    """Show numbered menu loop using plain input."""
    while True:
        print("1) type  2) drill  3) leetcode  4) stats  5) quit")
        try:
            choice: str = input("select: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nexited cleanly")
            return
        if choice in ("5", "q", "quit", "exit"):
            return
        if choice == "1":
            print("typing test coming in slice 02")
        elif choice == "2":
            print("drill coming in slice 04")
        elif choice == "3":
            print("usage: idle lc {login,list,show,pick,daily,start,test,submit,stats,open}")
        elif choice == "4":
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
