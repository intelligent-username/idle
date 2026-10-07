"""CLI command handlers for Codewars integration."""

import getpass
import os
from pathlib import Path
import subprocess
import sys
from typing import Any
import webbrowser

from idle.cw import api as cw_api
from idle.cw.auth import (
    load_auth,
    load_saved_credentials,
    save_auth,
    validate_credentials,
)
from idle.cw.render import format_kata_detail
from idle.cw.scaffold import _resolve_workdir, scaffold_kata


def _find_kata_file(slug: str) -> Path | None:
    """Find scaffolded python file for kata."""
    from idle.cw.scaffold import _sanitize_slug

    clean_slug = _sanitize_slug(slug)
    workdir = _resolve_workdir()
    candidates = [
        workdir / f"cw_{clean_slug}.py",
        workdir / f"{clean_slug}.py",
    ]
    for c in candidates:
        if c.is_file():
            return c
    return None


def cmd_login() -> None:
    """Interactive login for Codewars API key and username."""
    saved_key, saved_user = load_saved_credentials()
    print("Codewars Authentication Setup")
    print("Find your API key at: https://www.codewars.com/users/edit (bottom of page)")
    print("-" * 60)

    prompt_user = f"Codewars Username [{saved_user}]: " if saved_user else "Codewars Username: "
    try:
        username = input(prompt_user).strip() or saved_user
    except (EOFError, KeyboardInterrupt):
        print("\nexited cleanly")
        return

    prompt_key = f"API Key [{'set' if saved_key else 'optional'}]: "
    try:
        api_key = input(prompt_key).strip() or saved_key
    except (EOFError, KeyboardInterrupt):
        print("\nexited cleanly")
        return

    if not username and not api_key:
        print("login cancelled: empty credentials")
        return

    print("Validating with Codewars API...")
    ok, msg = validate_credentials(api_key=api_key, username=username)
    if ok:
        save_auth(api_key=api_key, username=username)
        print(f"Success: {msg}")
    else:
        save_auth(api_key=api_key, username=username)
        print(f"Saved (warning: {msg})")


def cmd_list(
    rank: str | None = None,
    tag: list[str] | None = None,
    status: str | None = None,
    limit: int = 20,
    refresh: bool = False,
) -> None:
    """List katas filtered by rank, tag, or status."""
    _, username = load_saved_credentials()
    try:
        katas = cw_api.fetch_kata_list(username=username, refresh=refresh)
    except (OSError, RuntimeError) as exc:
        print(f"Error fetching kata list: {exc}")
        return

    filtered: list[dict[str, Any]] = []
    for k in katas:
        rank_name = (k.get("rank") or {}).get("name", "").lower()
        if rank and rank.lower() not in rank_name:
            continue
        if tag:
            k_tags = [t.lower() for t in k.get("tags", [])]
            if not any(t.lower() in k_tags for t in tag):
                continue
        if status and k.get("status") != status:
            continue
        filtered.append(k)

    slice_katas = filtered[: max(limit, 0)]
    if not slice_katas:
        print("No katas match the specified filters.")
        return

    print(f"{'RANK':<8}  {'TITLE':<40}  {'STATUS':<8}  {'TAGS'}")
    print("-" * 75)
    for k in slice_katas:
        r_name = (k.get("rank") or {}).get("name", "")
        title = (k.get("name") or "")[:38]
        stat = "SOLVED" if k.get("status") == "ac" else "TODO"
        tags = ", ".join(k.get("tags", [])[:2])
        print(f"{r_name:<8}  {title:<40}  {stat:<8}  {tags}")


def cmd_show(id_or_slug: str) -> None:
    """Show kata description and details."""
    if not id_or_slug:
        print("usage: idle cw show <slug_or_id>")
        return
    try:
        kata = cw_api.fetch_kata(id_or_slug)
        detail = format_kata_detail(kata)
        import pydoc
        pydoc.pager(detail)
    except (OSError, RuntimeError) as exc:
        print(f"Could not load kata: {exc}")


def cmd_pick(rank: str | None = None, tag: list[str] | None = None) -> None:
    """Pick a random unsolved kata."""
    import random

    _, username = load_saved_credentials()
    katas = cw_api.fetch_kata_list(username=username)
    unsolved = [k for k in katas if k.get("status") != "ac"]

    if rank:
        unsolved = [k for k in unsolved if rank.lower() in (k.get("rank") or {}).get("name", "").lower()]
    if tag:
        unsolved = [k for k in unsolved if any(t.lower() in [kt.lower() for kt in k.get("tags", [])] for t in tag)]

    if not unsolved:
        print("No unsolved katas match your filters.")
        return

    chosen = random.choice(unsolved)
    r_name = (chosen.get("rank") or {}).get("name", "")
    print(f"Selected: {chosen.get('name')} [{r_name}]")
    print(f"Slug: {chosen.get('slug')}")
    try:
        ans = input("Scaffold solution file? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nexited cleanly")
        return
    if ans in ("y", "yes"):
        cmd_start(chosen.get("slug", ""))


def cmd_daily() -> None:
    """Display the daily kata."""
    try:
        kata = cw_api.fetch_daily()
        detail = format_kata_detail(kata)
        import pydoc
        pydoc.pager(detail)
    except (OSError, RuntimeError) as exc:
        print(f"Could not load daily kata: {exc}")


def cmd_start(id_or_slug: str) -> None:
    """Scaffold a solution file for the kata."""
    if not id_or_slug:
        print("usage: idle cw start <slug_or_id>")
        return
    try:
        kata = cw_api.fetch_kata(id_or_slug)
    except (OSError, RuntimeError) as exc:
        print(f"Could not fetch kata details: {exc}")
        return

    file_path = scaffold_kata(kata)
    print(f"Scaffolded solution file: {file_path}")


def cmd_test(id_or_slug: str | None = None) -> None:
    """Run local tests for the kata solution."""
    if not id_or_slug:
        print("usage: idle cw test <slug_or_id>")
        return
    file_path = _find_kata_file(id_or_slug)
    if not file_path:
        print(f"Solution file for '{id_or_slug}' not found. Run: idle cw start {id_or_slug}")
        return

    print(f"Running tests in {file_path.name}...")
    res = subprocess.run([sys.executable, str(file_path)], capture_output=True, text=True)
    if res.stdout:
        print(res.stdout)
    if res.stderr:
        print(res.stderr, file=sys.stderr)
    if res.returncode == 0:
        print("Result: PASSED")
    else:
        print(f"Result: FAILED (exit code {res.returncode})")


def cmd_submit(id_or_slug: str | None = None) -> None:
    """Submit kata solution or open submit page."""
    if not id_or_slug:
        print("usage: idle cw submit <slug_or_id>")
        return
    file_path = _find_kata_file(id_or_slug)
    if not file_path:
        print(f"Solution file for '{id_or_slug}' not found.")
        return

    url = f"https://www.codewars.com/kata/{id_or_slug}/train/python"
    print(f"Local solution file: {file_path.name}")
    print(f"To submit officially to Codewars, complete or paste in the browser editor:")
    print(f"  {url}")
    try:
        ans = input("Open browser to submit? [Y/n]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return
    if ans not in ("n", "no"):
        webbrowser.open(url)


def cmd_cw_stats() -> None:
    """View user Codewars stats."""
    _, username = load_saved_credentials()
    if not username:
        print("No Codewars username configured. Run: idle cw login")
        return
    try:
        user_data = cw_api.fetch_user(username)
    except (OSError, RuntimeError) as exc:
        print(f"Could not load stats: {exc}")
        return

    ranks = user_data.get("ranks", {})
    overall = ranks.get("overall", {})
    languages = ranks.get("languages", {})

    print(f"User: {user_data.get('username')}")
    print(f"Rank: {overall.get('name', 'N/A')}")
    print(f"Honor: {user_data.get('honor', 0)}")
    print(f"Leaderboard Position: #{user_data.get('leaderboardPosition', 'N/A')}")
    print(f"Total Completed: {user_data.get('codeChallenges', {}).get('totalCompleted', 0)}")
    if languages:
        print("\nLanguages:")
        for lang, info in languages.items():
            print(f"  - {lang}: {info.get('name')} ({info.get('score')} pts)")


def cmd_open(id_or_slug: str) -> None:
    """Open kata in web browser."""
    if not id_or_slug:
        print("usage: idle cw open <slug_or_id>")
        return
    url = f"https://www.codewars.com/kata/{id_or_slug}"
    webbrowser.open(url)
    print(f"Opened {url}")
