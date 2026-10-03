"""LeetCode terminal commands for list, show, solve loop."""

from pathlib import Path
from typing import Any

from idle.lc.scaffold import _resolve_workdir, strip_header

RELOGIN_MSG = "Session expired. Run: idle lc login"
DIFF_MAP = {"e": "Easy", "m": "Medium", "h": "Hard"}


def _norm_diff(raw: str | None) -> str | None:
    """Map e/m/h or full name to Easy/Medium/Hard."""
    if not raw:
        return None
    key: str = raw.strip().lower()
    if key in DIFF_MAP:
        return DIFF_MAP[key]
    for full in DIFF_MAP.values():
        if key == full.lower():
            return full
    return raw


def _status_label(raw: Any) -> str:
    """Map raw status to solved or todo."""
    return "solved" if str(raw).lower() == "ac" else "todo"


def _print_offline(action: str) -> None:
    """Print friendly offline message without traceback."""
    print(f"could not {action} (offline?). Check network and retry.")


def _matches(
    item: dict[str, Any],
    difficulty: str | None,
    tags: list[str] | None,
    status: str | None,
) -> bool:
    """Check one problem against filters."""
    if difficulty and str(item.get("difficulty", "")).lower() != difficulty.lower():
        return False
    if status:
        want: str = status.strip().lower()
        have: str = _status_label(item.get("status"))
        if want != have:
            return False
    if tags:
        have_tags: Any = item.get("tags", [])
        lower: list[str] = [str(t).lower() for t in have_tags if str(t)]
        for tag in tags:
            if str(tag).lower() not in lower:
                return False
    return True


def _filter_problems(
    problems: list[dict[str, Any]],
    difficulty: str | None,
    tags: list[str] | None,
    status: str | None,
) -> list[dict[str, Any]]:
    """Filter problems by difficulty, tags, and status."""
    want_diff: str | None = _norm_diff(difficulty)
    return [p for p in problems if _matches(p, want_diff, tags, status)]


def _print_list_table(problems: list[dict[str, Any]]) -> None:
    """Print plain table with id title diff acc tags status."""
    print(f"{'id':>5}  {'title':<40}  {'diff':<6}  {'acc':>6}  tags  status")
    for item in problems:
        pid: str = str(item.get("id", ""))
        title: str = str(item.get("title", ""))[:40]
        diff: str = str(item.get("difficulty", ""))
        acc: Any = item.get("ac_rate")
        try:
            acc_s: str = f"{float(acc):.1f}%" if acc is not None else "-"
        except (TypeError, ValueError):
            acc_s = "-"
        tags: Any = item.get("tags", [])
        tag_s: str = ",".join(str(t) for t in tags) if tags else "-"
        stat: str = _status_label(item.get("status"))
        print(f"{pid:>5}  {title:<40}  {diff:<6}  {acc_s:>6}  {tag_s}  {stat}")


def _find_in_list(
    problems: list[dict[str, Any]], key: str
) -> dict[str, Any] | None:
    """Find problem by id or slug, case insensitive."""
    want: str = key.strip().lower()
    for item in problems:
        if str(item.get("id", "")).lower() == want:
            return item
        if str(item.get("slug", "")).lower() == want:
            return item
    return None


def _fetch_list_safe(refresh: bool) -> list[dict[str, Any]] | None:
    """Fetch problem list, returning None on expected failure."""
    from idle.lc.api import AuthExpiredError
    from idle.lc import api as lc_api

    try:
        return lc_api.fetch_problem_list(refresh=refresh)
    except AuthExpiredError:
        print(RELOGIN_MSG)
        return None
    except (OSError, RuntimeError):
        _print_offline("fetch problem list")
        return None


def _resolve_slug(id_or_slug: str) -> str | None:
    """Resolve id or slug to canonical slug via cached list.

    Test: _resolve_slug mocked list returns slug for id "1".
    """
    problems: list[dict[str, Any]] | None = _fetch_list_safe(False)
    if problems is None:
        return None
    found: dict[str, Any] | None = _find_in_list(problems, id_or_slug)
    if found is None:
        print(f"problem not found: {id_or_slug}")
        return None
    return str(found.get("slug", ""))


def _resolve_detail(id_or_slug: str) -> dict[str, Any] | None:
    """Fetch fresh detail for id or slug, None on failure.

    Test: mocked fetch returns detail dict with slug key.
    """
    from idle.lc.api import AuthExpiredError
    from idle.lc import api as lc_api

    slug: str | None = _resolve_slug(id_or_slug)
    if not slug:
        return None
    try:
        return lc_api.fetch_question(slug)
    except AuthExpiredError:
        print(RELOGIN_MSG)
        return None
    except (OSError, RuntimeError):
        _print_offline("fetch problem detail")
        return None


def _format_detail(detail: dict[str, Any]) -> str:
    """Format header plus plain text body for pager."""
    from idle.lc.render import html_to_text

    fid: str = str(detail.get("id", ""))
    title: str = str(detail.get("title", ""))
    diff: str = str(detail.get("difficulty", ""))
    tags: Any = detail.get("tags", [])
    tag_s: str = ",".join(str(t) for t in tags) if tags else "-"
    slug: str = str(detail.get("slug", ""))
    url: str = f"https://leetcode.com/problems/{slug}/"
    body: str = html_to_text(str(detail.get("content_html", "")))
    sample: str = str(detail.get("sample_test_case", "") or "")
    head: str = f"{fid}. {title} [{diff}] ({url}) Tags: {tag_s}\n\n"
    if sample:
        return head + body + "\n\nSample:\n" + sample
    return head + body


def _show_detail(detail: dict[str, Any]) -> None:
    """Render detail through pager."""
    import pydoc

    text: str = _format_detail(detail)
    pydoc.pager(text)


def _login_direct(username: str) -> None:
    """Login with username password and save cookies."""
    import getpass

    from idle.lc.auth import login_username_password
    from idle.lc.auth import save_auth

    try:
        password: str = getpass.getpass("password: ")
    except (EOFError, KeyboardInterrupt):
        print("\nexited cleanly")
        return
    try:
        cookies: dict[str, str] = login_username_password(username, password)
    except (OSError, RuntimeError) as exc:
        print(str(exc))
        return
    save_auth(cookies)
    print("saved login")


def cmd_login() -> None:
    """Prompt for cookies or username password and save."""
    from idle.lc.auth import save_auth

    try:
        session: str = input("LEETCODE_SESSION: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nexited cleanly")
        return
    if session:
        try:
            csrf: str = input("csrftoken: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nexited cleanly")
            return
        cookies: dict[str, str] = {"LEETCODE_SESSION": session}
        if csrf:
            cookies["csrftoken"] = csrf
        save_auth(cookies)
        print("saved login")
        return
    try:
        username: str = input("username: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nexited cleanly")
        return
    if not username:
        print("login cancelled: empty session")
        return
    _login_direct(username)


def cmd_list(
    difficulty: str | None = None,
    tag: list[str] | None = None,
    status: str | None = None,
    limit: int = 20,
    refresh: bool = False,
) -> None:
    """List problems with filters and plain table.

    Test: mocked list of 3, filter Easy gives 1 row.
    """
    problems: list[dict[str, Any]] | None = _fetch_list_safe(refresh)
    if problems is None:
        return
    rows: list[dict[str, Any]] = _filter_problems(problems, difficulty, tag, status)
    _print_list_table(rows[: max(limit, 0)])


def cmd_show(id_or_slug: str) -> None:
    """Show one problem via pager."""
    detail: dict[str, Any] | None = _resolve_detail(id_or_slug)
    if detail is None:
        return
    _show_detail(detail)


def cmd_pick(
    difficulty: str | None = None, tag: list[str] | None = None
) -> None:
    """Pick random unsolved problem and offer scaffold."""
    import random

    problems: list[dict[str, Any]] | None = _fetch_list_safe(False)
    if problems is None:
        return
    rows: list[dict[str, Any]] = _filter_problems(problems, difficulty, tag, "todo")
    if not rows:
        print("no unsolved problems match filters")
        return
    choice: dict[str, Any] = random.choice(rows)
    print(f"{choice.get('id')}. {choice.get('title')} [{choice.get('difficulty')}]")
    try:
        ans: str = input("scaffold? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\nexited cleanly")
        return
    if ans in ("y", "yes"):
        cmd_start(str(choice.get("slug", "")))


def cmd_daily() -> None:
    """Show daily challenge via pager."""
    from idle.lc.api import AuthExpiredError
    from idle.lc import api as lc_api

    try:
        detail: dict[str, Any] = lc_api.fetch_daily()
    except AuthExpiredError:
        print(RELOGIN_MSG)
        return
    except (OSError, RuntimeError):
        _print_offline("fetch daily challenge")
        return
    _show_detail(detail)


def cmd_start(id_or_slug: str) -> None:
    """Scaffold solution dir for problem.

    Test: mocked detail scaffolds solution.py path.
    """
    from idle.lc.scaffold import scaffold_problem

    detail: dict[str, Any] | None = _resolve_detail(id_or_slug)
    if detail is None:
        return
    try:
        path: Path = scaffold_problem(detail)
    except OSError:
        print("could not write scaffold (disk?).")
        return
    print(f"scaffolded: {path}")


def _lc_lang() -> str:
    """Return configured lc language, default python3."""
    from idle.config import load_config

    try:
        cfg: dict[str, Any] = load_config()
    except OSError:
        return "python3"
    lc: Any = cfg.get("lc", {})
    if isinstance(lc, dict) and str(lc.get("language", "")):
        return str(lc["language"])
    return "python3"


def _read_pair(
    detail: dict[str, Any], sol: Path, tst: Path
) -> tuple[dict[str, Any], str, str]:
    """Read code and data input for detail."""
    code: str = strip_header(sol.read_text(encoding="utf-8"))
    data_in: str = tst.read_text(encoding="utf-8") if tst.exists() else ""
    if not data_in.strip():
        data_in = str(detail.get("sample_test_case", "") or "")
    return (detail, code, data_in)


def _load_solution(
    id_or_slug: str | None,
) -> tuple[dict[str, Any], str, str] | None:
    """Load detail, code, and data input for test or submit.

    Test: tmp workdir with solution.py returns code string.
    """
    if id_or_slug:
        detail: dict[str, Any] | None = _resolve_detail(id_or_slug)
        if detail is None:
            return None
        fid: str = str(detail.get("id", ""))
        slug: str = str(detail.get("slug", ""))
        base: Path = _resolve_workdir(None) / f"{fid}-{slug}"
        sol: Path = base / "solution.py"
        if not sol.exists():
            print(f"no solution yet. Run: idle lc start {detail.get('slug')}")
            return None
        return _read_pair(detail, sol, base / "test.txt")
    cwd_sol: Path = Path.cwd() / "solution.py"
    if not cwd_sol.exists():
        print("no solution found. Run: idle lc start <id>")
        return None
    return _load_cwd_solution(cwd_sol)


def _load_cwd_solution(sol: Path) -> tuple[dict[str, Any], str, str] | None:
    """Load solution from current dir using folder name."""
    folder: str = sol.parent.name
    slug: str = folder.split("-", 1)[1] if "-" in folder else folder
    detail: dict[str, Any] | None = _resolve_detail(slug)
    if detail is None:
        return None
    return _read_pair(detail, sol, sol.parent / "test.txt")


def _verdict_str(result: dict[str, Any]) -> str:
    """Extract verdict string from varied result shapes."""
    for key in ("status_msg", "status", "state", "verdict"):
        val: Any = result.get(key)
        if isinstance(val, str) and val.strip():
            return val
    if result.get("run_success") is True:
        return "Accepted"
    if result.get("run_success") is False:
        return "Wrong Answer"
    return "Unknown"


def _print_runtime(result: dict[str, Any]) -> None:
    """Print runtime, percentile, and memory lines."""
    runtime: Any = result.get("status_runtime") or result.get("runtime")
    if runtime:
        print(f"runtime: {runtime}")
    perc: Any = result.get("runtime_percentile")
    if perc is not None:
        print(f"percentile: {perc}")
    mem: Any = result.get("status_memory") or result.get("memory")
    if mem:
        print(f"memory: {mem}")
    memp: Any = result.get("memory_percentile")
    if memp is not None:
        print(f"memory percentile: {memp}")


def _print_failure(result: dict[str, Any]) -> None:
    """Print expected vs actual and failing input."""
    exp: Any = result.get("expected_output") or result.get("expected")
    got: Any = result.get("code_output") or result.get("actual")
    if exp is not None or got is not None:
        print(f"expected: {exp}")
        print(f"actual: {got}")
    case: Any = result.get("last_testcase") or result.get("input")
    if case:
        print(f"failing input: {case}")
    err: Any = result.get("full_compile_error") or result.get("error")
    if err:
        print(f"error: {err}")


def _display_result(result: dict[str, Any]) -> None:
    """Display verdict, runtime, memory, and diffs."""
    print(f"verdict: {_verdict_str(result)}")
    _print_runtime(result)
    _print_failure(result)


def _parse_runtime_ms(result: dict[str, Any]) -> int | None:
    """Parse runtime_ms int from result shapes."""
    raw: Any = result.get("runtime_ms")
    if isinstance(raw, int):
        return raw
    text: Any = result.get("status_runtime") or result.get("runtime")
    if isinstance(text, str):
        digits: str = "".join(c for c in text if c.isdigit())
        if digits:
            try:
                return int(digits)
            except ValueError:
                return None
    return None


def _parse_memory_mb(result: dict[str, Any]) -> float | None:
    """Parse memory_mb float from result shapes."""
    raw: Any = result.get("memory_mb")
    if isinstance(raw, (int, float)):
        return float(raw)
    text: Any = result.get("status_memory") or result.get("memory")
    if isinstance(text, str):
        num: str = "".join(c for c in text if c.isdigit() or c == ".")
        try:
            return float(num) if num else None
        except ValueError:
            return None
    return None


def _record_attempt(
    problem_id: int, kind: str, verdict: str, result: dict[str, Any]
) -> None:
    """Insert one row into lc_attempts table."""
    from datetime import datetime, timezone

    from idle.config import resolve_paths
    from idle.db import get_db

    lang: str = _lc_lang()
    now: str = datetime.now(timezone.utc).isoformat()
    rt: int | None = _parse_runtime_ms(result)
    mm: float | None = _parse_memory_mb(result)
    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        conn.execute(
            "INSERT INTO lc_attempts(problem_id, ts, kind, lang,"
            " verdict, runtime_ms, memory_mb) VALUES(?,?,?,?,?,?,?);",
            (problem_id, now, kind, lang, verdict, rt, mm),
        )
        conn.commit()
    finally:
        conn.close()


def _mark_solved(problem_id: int) -> None:
    """Mark problem solved, preserving started_at."""
    from datetime import datetime, timezone

    from idle.config import resolve_paths
    from idle.db import get_db

    now: str = datetime.now(timezone.utc).isoformat()
    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT started_at FROM lc_progress WHERE problem_id=?;",
            (problem_id,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO lc_progress(problem_id, status,"
                " started_at, solved_at) VALUES(?,?,?,?);",
                (problem_id, "solved", now, now),
            )
        else:
            conn.execute(
                "UPDATE lc_progress SET status='solved',"
                " solved_at=? WHERE problem_id=?;",
                (now, problem_id),
            )
        conn.commit()
    finally:
        conn.close()


def _problem_num(detail: dict[str, Any]) -> int | None:
    """Return numeric frontend id or None."""
    try:
        return int(str(detail.get("id", "")))
    except ValueError:
        return None


def cmd_test(id_or_slug: str | None = None) -> None:
    """Run remote sample then local fallback and show verdict.

    Test: mocked run returns verdict dict for display.
    """
    from idle.lc.api import AuthExpiredError
    from idle.lc import api as lc_api

    loaded = _load_solution(id_or_slug)
    if loaded is None:
        return
    detail, code, data_in = loaded
    slug: str = str(detail.get("slug", ""))
    qid: str = str(detail.get("question_id", "") or detail.get("id", ""))
    try:
        result: dict[str, Any] = lc_api.run_sample(
            slug, qid, code, data_in, _lc_lang()
        )
    except AuthExpiredError:
        print(RELOGIN_MSG)
        return
    except (OSError, RuntimeError):
        try:
            result = lc_api.run_local(code, data_in)
        except (OSError, RuntimeError):
            _print_offline("run test")
            return
    _display_result(result)
    num: int | None = _problem_num(detail)
    if num is not None:
        _record_attempt(num, "test", _verdict_str(result), result)


def _do_remote_submit(
    detail: dict[str, Any], code: str
) -> dict[str, Any] | None:
    """Submit remotely and poll to SUCCESS, None on failure."""
    from idle.lc.api import AuthExpiredError
    from idle.lc import api as lc_api

    slug: str = str(detail.get("slug", ""))
    qid: str = str(detail.get("question_id", "") or detail.get("id", ""))
    try:
        resp: dict[str, Any] = lc_api.submit_solution(slug, qid, code, _lc_lang())
        sid: Any = resp.get("submission_id") or resp.get("submissionId")
        if sid is None:
            alt: Any = resp.get("submission")
            if isinstance(alt, dict):
                sid = (
                    alt.get("id")
                    or alt.get("submission_id")
                    or alt.get("submissionId")
                )
            elif alt is not None:
                sid = alt
        if sid is None:
            sid = resp.get("id")
        if sid is None:
            print("submit failed: no submission id")
            return None
        return lc_api.poll_verdict(sid)
    except AuthExpiredError:
        print(RELOGIN_MSG)
        return None
    except (OSError, RuntimeError):
        _print_offline("submit solution")
        return None


def cmd_submit(id_or_slug: str | None = None) -> None:
    """Submit solution, poll to SUCCESS, record progress.

    Test: mocked submit plus SUCCESS poll marks solved.
    """
    loaded = _load_solution(id_or_slug)
    if loaded is None:
        return
    detail, code, _ = loaded
    verdict: dict[str, Any] | None = _do_remote_submit(detail, code)
    if verdict is None:
        return
    _display_result(verdict)
    num: int | None = _problem_num(detail)
    if num is None:
        return
    _record_attempt(num, "submit", _verdict_str(verdict), verdict)
    if "accept" in _verdict_str(verdict).lower():
        _mark_solved(num)


def cmd_open(id_or_slug: str) -> None:
    """Open problem URL in browser."""
    slug: str | None = _resolve_slug(id_or_slug)
    if not slug:
        return
    import webbrowser

    url: str = f"https://leetcode.com/problems/{slug}/"
    try:
        webbrowser.open(url)
    except Exception:
        print(f"open manually: {url}")
        return
    print(f"opened: {url}")


def _calc_streak(days: list[str]) -> int:
    """Count consecutive-day streak ending at latest date."""
    from datetime import date

    uniq: list[str] = sorted(set(days))
    if not uniq:
        return 0
    parsed: list[date] = []
    for day in uniq:
        try:
            parsed.append(date.fromisoformat(day))
        except ValueError:
            continue
    if not parsed:
        return 0
    streak: int = 1
    for i in range(len(parsed) - 1, 0, -1):
        if (parsed[i] - parsed[i - 1]).days == 1:
            streak += 1
        else:
            break
    return streak


def _print_by_difficulty(conn: Any) -> None:
    """Print solved counts grouped by difficulty."""
    rows = conn.execute(
        "SELECT p.difficulty, COUNT(*) FROM lc_problems p"
        " JOIN lc_progress g ON p.id=g.problem_id"
        " WHERE g.status='solved' GROUP BY p.difficulty;"
    ).fetchall()
    if not rows:
        print("solved: 0")
        return
    for diff, count in rows:
        print(f"solved {diff}: {count}")


def _print_recent(conn: Any) -> None:
    """Print recent attempts table."""
    rows = conn.execute(
        "SELECT problem_id, ts, kind, verdict FROM lc_attempts"
        " ORDER BY id DESC LIMIT 10;"
    ).fetchall()
    if not rows:
        print("no attempts yet")
        return
    for pid, ts, kind, verdict in rows:
        print(f"{pid} {ts} {kind} {verdict}")


def _print_streak(conn: Any) -> None:
    """Print solve-day streak count."""
    rows = conn.execute(
        "SELECT substr(solved_at,1,10) FROM lc_progress"
        " WHERE solved_at IS NOT NULL;"
    ).fetchall()
    days: list[str] = [str(r[0]) for r in rows if r[0]]
    print(f"streak: {_calc_streak(days)} days ({len(set(days))} active)")


def cmd_lc_stats() -> None:
    """Show solved by difficulty, recent attempts, streak."""
    from idle.config import resolve_paths
    from idle.db import get_db

    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        _print_by_difficulty(conn)
        _print_recent(conn)
        _print_streak(conn)
    finally:
        conn.close()
