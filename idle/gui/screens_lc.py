"""LeetCode pygame screens: list, detail, solve editor, login."""

from dataclasses import dataclass, field
from typing import Any

from idle.gui.widgets import ScrollableList, Textbox
from idle.lc.commands import RELOGIN_MSG
from idle.lc.scaffold import strip_header

__all__: list[str] = [
    "LcDetailState",
    "LcFilters",
    "LcListState",
    "LcLoginState",
    "LcSolveState",
    "apply_lc_filters",
    "auth_needed",
    "draw_lc_detail",
    "draw_lc_list",
    "draw_lc_login",
    "draw_lc_solve",
    "editor_seed",
    "format_problem_row",
    "format_verdict_panel",
    "handle_lc_detail",
    "handle_lc_list",
    "handle_lc_login",
    "handle_lc_solve",
    "load_daily",
    "load_detail",
    "load_problem_list",
    "open_problem",
    "pick_random_problem",
    "refresh_problem_list",
    "repick_random",
    "run_submit_action",
    "run_test_action",
    "scaffold_to_disk",
    "toggle_new_only",
    "try_login_password",
    "try_save_login",
    "verdict_summary",
]

LOGIN_SAVED_MSG: str = "saved login"
LOGIN_EMPTY_MSG: str = "login cancelled: empty session"
LIMIT_MIN: int = 5
LIMIT_MAX: int = 200
LIMIT_STEP: int = 5
DIFF_CYCLE: list[str | None] = [None, "Easy", "Medium", "Hard"]
STATUS_CYCLE: list[str | None] = [None, "todo", "solved"]


@dataclass
class LcFilters:
    """Filter values for LC list."""

    difficulty: str | None = None
    tag: str | None = None
    status: str | None = None
    limit: int = 20


@dataclass
class LcListState:
    """List view state with filters and selection."""

    problems: list[dict[str, Any]] = field(default_factory=list)
    filters: LcFilters = field(default_factory=LcFilters)
    items: ScrollableList = field(default_factory=lambda: ScrollableList([]))
    message: str = ""
    needs_login: bool = False
    tag_edit: bool = False
    tag_box: Textbox = field(default_factory=Textbox)
    new_only: bool = True
    current: dict[str, Any] | None = None


@dataclass
class LcDetailState:
    """Detail view state with scrollable text."""

    slug: str = ""
    detail: dict[str, Any] | None = None
    text: str = ""
    lines: list[str] = field(default_factory=list)
    scroll: int = 0
    message: str = ""
    needs_login: bool = False


@dataclass
class LcSolveState:
    """Solve view state with editor and verdict."""

    slug: str = ""
    detail: dict[str, Any] = field(default_factory=dict)
    editor: Textbox = field(default_factory=lambda: Textbox(multiline=True))
    verdict: dict[str, Any] | None = None
    panel: str = ""
    message: str = ""
    needs_login: bool = False
    solved: bool = False
    data_input: str = ""


@dataclass
class LcLoginState:
    """Login form state with username and password."""

    session_box: Textbox = field(default_factory=Textbox)
    csrf_box: Textbox = field(default_factory=Textbox)
    username_box: Textbox = field(default_factory=Textbox)
    password_box: Textbox = field(default_factory=Textbox)
    focus: int = 0
    message: str = ""
    saved: bool = False


def format_problem_row(item: dict[str, Any]) -> str:
    """Format one problem row for list display."""
    from idle.lc.commands import _status_label

    pid: str = str(item.get("id", ""))
    title: str = str(item.get("title", ""))[:38]
    diff: str = str(item.get("difficulty", ""))
    stat: str = _status_label(item.get("status"))
    return f"{pid:>5}  {title:<38}  {diff:<6}  {stat}"


def _tags_arg(tag: str | None) -> list[str] | None:
    """Convert single tag string to filter list."""
    if tag is None:
        return None
    cleaned: str = tag.strip()
    if not cleaned:
        return None
    return [cleaned]


def apply_lc_filters(
    problems: list[dict[str, Any]],
    difficulty: str | None,
    tag: str | None,
    status: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Filter problems then slice to limit.

    Test: 3 rows, Easy filter gives 1 row.
    """
    from idle.lc.commands import _filter_problems

    rows: list[dict[str, Any]] = _filter_problems(
        problems, difficulty, _tags_arg(tag), status
    )
    cut: int = max(0, limit)
    return rows[:cut]


def _offline_text(action: str) -> str:
    """Build friendly offline message for action."""
    return f"could not {action} (offline?). Check network and retry."


def _network_message(exc: Exception, action: str) -> str:
    """Return challenge text when detected else offline text."""
    from idle.lc.auth import is_challenge

    msg: str = str(exc).strip()
    if msg and is_challenge(msg):
        return msg
    return _offline_text(action)


def verdict_summary(result: dict[str, Any]) -> str:
    """Return single line verdict string."""
    from idle.lc.commands import _verdict_str

    return _verdict_str(result)


def _runtime_lines(result: dict[str, Any]) -> list[str]:
    """Collect runtime and memory lines for panel."""
    lines: list[str] = []
    runtime: Any = result.get("status_runtime") or result.get("runtime")
    if runtime:
        lines.append(f"runtime: {runtime}")
    perc: Any = result.get("runtime_percentile")
    if perc is not None:
        lines.append(f"percentile: {perc}")
    mem: Any = result.get("status_memory") or result.get("memory")
    if mem:
        lines.append(f"memory: {mem}")
    memp: Any = result.get("memory_percentile")
    if memp is not None:
        lines.append(f"memory percentile: {memp}")
    return lines


def _failure_lines(result: dict[str, Any]) -> list[str]:
    """Collect expected, actual, failing input, error lines."""
    lines: list[str] = []
    exp: Any = result.get("expected_output") or result.get("expected")
    got: Any = result.get("code_output") or result.get("actual")
    if exp is not None or got is not None:
        lines.append(f"expected: {exp}")
        lines.append(f"actual: {got}")
    case: Any = result.get("last_testcase") or result.get("input")
    if case:
        lines.append(f"failing input: {case}")
    err: Any = result.get("full_compile_error") or result.get("error")
    if err:
        lines.append(f"error: {err}")
    return lines


def format_verdict_panel(result: dict[str, Any]) -> str:
    """Format verdict plus runtime, memory, failing case.

    Test: dict with status_msg Accepted gives verdict line.
    """
    head: str = f"verdict: {verdict_summary(result)}"
    rest: list[str] = _runtime_lines(result) + _failure_lines(result)
    if not rest:
        return head
    return head + "\n" + "\n".join(rest)


def editor_seed(detail: dict[str, Any], lang: str = "python3") -> str:
    """Pick starter code for editor from detail snippets."""
    raw: Any = detail.get("code_snippets")
    seed: str = ""
    if isinstance(raw, dict):
        if isinstance(raw.get(lang), str) and str(raw[lang]).strip():
            seed = str(raw[lang])
        elif isinstance(raw.get("python3"), str):
            seed = str(raw["python3"])
        else:
            for value in raw.values():
                if isinstance(value, str) and value.strip():
                    seed = value
                    break
    if not seed.endswith("\n") and seed:
        seed += "\n"
    return seed


def _sample_input(detail: dict[str, Any]) -> str:
    """Return sample test input for detail."""
    sample: Any = detail.get("sample_test_case") or detail.get(
        "example_testcases", ""
    )
    text: str = str(sample or "")
    if text and not text.endswith("\n"):
        text += "\n"
    return text


def load_problem_list(refresh: bool = False) -> tuple[list[dict[str, Any]], str, bool]:
    """Fetch problem list with friendly offline and expiry signals.

    Test: mocked fetch returns 2 rows, no login flag.
    """
    from idle.lc import api as lc_api
    from idle.lc.api import AuthExpiredError

    try:
        problems: list[dict[str, Any]] = lc_api.fetch_problem_list(
            refresh=refresh
        )
    except AuthExpiredError:
        return [], RELOGIN_MSG, True
    except (OSError, RuntimeError) as exc:
        return [], _network_message(exc, "fetch problem list"), False
    return problems, "", False


def pick_random_problem(
    problems: list[dict[str, Any]],
    new_only: bool,
    difficulty: str | None = None,
    tag: str | None = None,
    status: str | None = None,
) -> dict[str, Any] | None:
    """Pick one random problem, todo-only when new_only."""
    import random

    from idle.lc.commands import _filter_problems

    want_status: str | None = "todo" if new_only else status
    want_tag: list[str] | None = _tags_arg(tag)
    rows: list[dict[str, Any]] = _filter_problems(
        problems, difficulty, want_tag, want_status
    )
    if not rows:
        return None
    return random.choice(rows)


def _rebuild_list_items(view: LcListState) -> None:
    """Pick single random row respecting new_only, no bulk list."""
    pick: dict[str, Any] | None = pick_random_problem(
        view.problems,
        view.new_only,
        view.filters.difficulty,
        view.filters.tag,
        view.filters.status,
    )
    view.current = pick
    if pick is None:
        view.items = ScrollableList([])
        return
    labels: list[str] = [format_problem_row(pick)]
    view.items = ScrollableList(labels, selected=0, visible_count=12)


def toggle_new_only(view: LcListState) -> None:
    """Toggle new-only filter and repick single random."""
    view.new_only = not view.new_only
    _rebuild_list_items(view)


def repick_random(view: LcListState) -> None:
    """Pick another random from cached problems, no network."""
    _rebuild_list_items(view)


def refresh_problem_list(view: LcListState, refresh: bool = False) -> None:
    """Reload problems into view, set message and login flag.

    Test: mocked list of 3 fills view items.
    """
    problems: list[dict[str, Any]]
    message: str
    login: bool
    problems, message, login = load_problem_list(refresh=refresh)
    if login:
        view.problems = []
        view.message = message
        view.needs_login = True
        view.items = ScrollableList([])
        return
    if message and not problems:
        view.message = message
        view.needs_login = False
        view.items = ScrollableList([])
        return
    view.problems = problems
    view.message = ""
    view.needs_login = False
    _rebuild_list_items(view)


def _resolve_key(
    problems: list[dict[str, Any]], key: str
) -> dict[str, Any] | None:
    """Find problem by id or slug in cached list."""
    from idle.lc.commands import _find_in_list

    return _find_in_list(problems, key)


def _detail_text(detail: dict[str, Any]) -> str:
    """Format detail header plus body for display."""
    from idle.lc.commands import _format_detail

    return _format_detail(detail)


def load_detail(id_or_slug: str) -> tuple[dict[str, Any] | None, str, str, bool]:
    """Fetch detail for id or slug with friendly messages.

    Test: mocked list plus question gives formatted text.
    """
    from idle.lc import api as lc_api
    from idle.lc.api import AuthExpiredError

    try:
        problems: list[dict[str, Any]] = lc_api.fetch_problem_list(refresh=False)
    except AuthExpiredError:
        return None, "", RELOGIN_MSG, True
    except (OSError, RuntimeError) as exc:
        return None, "", _network_message(exc, "fetch problem list"), False
    found: dict[str, Any] | None = _resolve_key(problems, id_or_slug)
    if found is None:
        return None, "", f"problem not found: {id_or_slug}", False
    slug: str = str(found.get("slug", ""))
    try:
        detail: dict[str, Any] = lc_api.fetch_question(slug)
    except AuthExpiredError:
        return None, "", RELOGIN_MSG, True
    except (OSError, RuntimeError) as exc:
        return None, "", _network_message(exc, "fetch problem detail"), False
    return detail, _detail_text(detail), "", False


def load_daily() -> tuple[dict[str, Any] | None, str, str, bool]:
    """Fetch daily challenge with friendly messages.

    Test: mocked fetch_daily returns detail with text.
    """
    from idle.lc import api as lc_api
    from idle.lc.api import AuthExpiredError

    try:
        detail: dict[str, Any] = lc_api.fetch_daily()
    except AuthExpiredError:
        return None, "", RELOGIN_MSG, True
    except (OSError, RuntimeError) as exc:
        return None, "", _network_message(exc, "fetch daily challenge"), False
    return detail, _detail_text(detail), "", False


def scaffold_to_disk(detail: dict[str, Any]) -> tuple[str, str]:
    """Scaffold solution files, return path and message."""
    from idle.lc.scaffold import scaffold_problem

    try:
        path = scaffold_problem(detail)
    except OSError:
        return "", "could not write scaffold (disk?)."
    return str(path), f"scaffolded: {path}"


def _qid_of(detail: dict[str, Any]) -> str:
    """Return question id string for API calls."""
    return str(detail.get("question_id", "") or detail.get("id", ""))


def _problem_num(detail: dict[str, Any]) -> int | None:
    """Return numeric problem id or None."""
    try:
        return int(str(detail.get("id", "")))
    except ValueError:
        return None


def _local_test_fallback(
    clean: str, text_in: str, detail: dict[str, Any]
) -> tuple[dict[str, Any] | None, str, bool]:
    """Run local fallback and format panel."""
    from idle.lc import api as lc_api
    from idle.lc.commands import _record_attempt

    try:
        local: dict[str, Any] = lc_api.run_local(clean, text_in)
    except (OSError, RuntimeError) as exc:
        return None, _network_message(exc, "run test"), False
    num: int | None = _problem_num(detail)
    if num is not None:
        _record_attempt(num, "test", verdict_summary(local), local)
    return local, format_verdict_panel(local), False


def _extract_sid(resp: dict[str, Any]) -> Any:
    """Return submission id tolerating varied keys."""
    sid: Any = resp.get("submission_id") or resp.get("submissionId")
    if sid is not None:
        return sid
    sid = resp.get("submission") or resp.get("id")
    if isinstance(sid, dict):
        return sid.get("submission_id") or sid.get("submissionId") or sid.get("id")
    return sid


def _record_submit(detail: dict[str, Any], verdict: dict[str, Any]) -> bool:
    """Record submit attempt and mark solved."""
    from idle.lc.commands import _mark_solved, _record_attempt

    num: int | None = _problem_num(detail)
    solved: bool = "accept" in verdict_summary(verdict).lower()
    if num is not None:
        _record_attempt(num, "submit", verdict_summary(verdict), verdict)
        if solved:
            _mark_solved(num)
    return solved


def run_test_action(
    detail: dict[str, Any], code: str, data_input: str
) -> tuple[dict[str, Any] | None, str, bool]:
    """Run remote test then local fallback.

    Test: mocked run_sample returns verdict dict with panel.
    """
    from idle.lc import api as lc_api
    from idle.lc.api import AuthExpiredError
    from idle.lc.commands import _record_attempt

    slug: str = str(detail.get("slug", ""))
    clean: str = strip_header(code)
    text_in: str = data_input
    if not text_in.strip():
        text_in = _sample_input(detail)
    try:
        result: dict[str, Any] = lc_api.run_sample(
            slug, _qid_of(detail), clean, text_in, "python3"
        )
    except AuthExpiredError:
        return None, RELOGIN_MSG, True
    except (OSError, RuntimeError):
        return _local_test_fallback(clean, text_in, detail)
    num: int | None = _problem_num(detail)
    if num is not None:
        _record_attempt(num, "test", verdict_summary(result), result)
    return result, format_verdict_panel(result), False


def run_submit_action(
    detail: dict[str, Any], code: str
) -> tuple[dict[str, Any] | None, str, bool, bool]:
    """Submit solution, poll verdict, record and mark solved.

    Test: mocked submit plus SUCCESS poll marks solved True.
    """
    from idle.lc import api as lc_api
    from idle.lc.api import AuthExpiredError

    slug: str = str(detail.get("slug", ""))
    clean: str = strip_header(code)
    try:
        resp: dict[str, Any] = lc_api.submit_solution(
            slug, _qid_of(detail), clean, "python3"
        )
    except AuthExpiredError:
        return None, RELOGIN_MSG, True, False
    except (OSError, RuntimeError) as exc:
        return None, _network_message(exc, "submit solution"), False, False
    sid: Any = _extract_sid(resp)
    if sid is None:
        return None, "submit failed: no submission id", False, False
    try:
        verdict: dict[str, Any] = lc_api.poll_verdict(sid)
    except AuthExpiredError:
        return None, RELOGIN_MSG, True, False
    except (OSError, RuntimeError) as exc:
        return None, _network_message(exc, "poll verdict"), False, False
    solved: bool = _record_submit(detail, verdict)
    return verdict, format_verdict_panel(verdict), False, solved


def open_problem(slug: str) -> str:
    """Open problem URL in browser with friendly message."""
    import webbrowser

    url: str = f"https://leetcode.com/problems/{slug}/"
    try:
        webbrowser.open(url)
    except Exception:
        return f"open manually: {url}"
    return f"opened: {url}"


def auth_needed() -> bool:
    """Check if login is required (no saved auth)."""
    from idle.lc.auth import load_auth

    return load_auth() is None


def try_save_login(session: str, csrf: str) -> tuple[bool, str]:
    """Save login cookies, never echo token values.

    Test: empty session returns False with cancel message.
    """
    from idle.lc.auth import save_auth

    if not session.strip():
        return False, LOGIN_EMPTY_MSG
    cookies: dict[str, str] = {"LEETCODE_SESSION": session.strip()}
    if csrf.strip():
        cookies["csrftoken"] = csrf.strip()
    save_auth(cookies)
    return True, LOGIN_SAVED_MSG


def try_login_password(username: str, password: str) -> tuple[bool, str]:
    """Login with password direct, no browser.

    Test: empty creds give False without network.
    """
    from idle.lc.auth import login_username_password, save_auth

    if not username.strip() or not password.strip():
        return False, "login failed: bad credentials or captcha"
    try:
        cookies: dict[str, str] = login_username_password(username, password)
    except (OSError, RuntimeError) as exc:
        msg: str = str(exc).strip()
        return False, msg if msg else _offline_text("login")
    save_auth(cookies)
    return True, LOGIN_SAVED_MSG


def make_solve_state(detail: dict[str, Any]) -> LcSolveState:
    """Build solve state with seeded editor for detail."""
    seed: str = editor_seed(detail)
    view: LcSolveState = LcSolveState(
        slug=str(detail.get("slug", "")),
        detail=detail,
        editor=Textbox(multiline=True, text=seed),
        data_input=_sample_input(detail),
    )
    return view


def make_detail_state(
    detail: dict[str, Any] | None, text: str, slug: str
) -> LcDetailState:
    """Build detail state with wrapped lines for scroll."""
    lines: list[str] = text.splitlines() if text else []
    return LcDetailState(slug=slug, detail=detail, text=text, lines=lines)


def _draw_text_lines(surface: Any, font: Any, lines: list[str], x: int, y: int) -> int:
    """Draw lines top to bottom, return next y."""
    from idle.gui import theme as theme_mod

    cur: int = y
    for line in lines:
        img = font.render(line, True, theme_mod.FG)
        surface.blit(img, (x, cur))
        cur += font.get_linesize()
    return cur


def _draw_bar(surface: Any, font: Any, text: str, y: int) -> None:
    """Draw single bar line at y."""
    from idle.gui import theme as theme_mod

    img = font.render(text[:120], True, theme_mod.DIM)
    surface.blit(img, (12, y))


def draw_lc_list(surface: Any, font: Any, view: LcListState) -> None:
    """Draw single random problem plus new-only checkbox."""
    import pygame

    from idle.gui import theme as theme_mod

    surface.fill(theme_mod.BG)
    w: int = surface.get_width()
    h: int = surface.get_height()
    filt: str = (
        f"d:{view.filters.difficulty or 'All'} "
        f"t:{view.filters.tag or 'All'}"
    )
    if view.tag_edit:
        filt += " [tag-edit Enter done]"
    _draw_bar(surface, font, "LC Random | " + filt, 8)
    check: str = "[x]" if view.new_only else "[ ]"
    _draw_bar(surface, font, f"{check} new problems only (n to toggle)", 30)
    if view.current is None:
        _draw_bar(
            surface,
            font,
            "no unsolved problems match filters. g retry, r refresh",
            58,
        )
    else:
        row = pygame.Rect(8, 56, w - 16, font.get_linesize() + 6)
        surface.fill(theme_mod.DIM, row)
        line: str = format_problem_row(view.current)[:110]
        img = font.render(line, True, theme_mod.FG)
        surface.blit(img, (12, 58))
        title: str = str(view.current.get("title", ""))[:100]
        diff: str = str(view.current.get("difficulty", ""))
        _draw_bar(surface, font, f"{title} [{diff}]", 86)
    _draw_bar(surface, font, view.message[:120] if view.message else "", h - 56)
    _draw_bar(
        surface,
        font,
        "g random n new-only d diff t tag r refresh Enter open Esc back",
        h - 28,
    )


def draw_lc_detail(surface: Any, font: Any, view: LcDetailState) -> None:
    """Draw scrollable detail text with footer."""
    from idle.gui import theme as theme_mod

    surface.fill(theme_mod.BG)
    h: int = surface.get_height()
    _draw_bar(surface, font, f"Detail {view.slug} | Up/Down scroll", 8)
    per: int = max(1, (h - 80) // max(1, font.get_linesize()))
    shown: list[str] = view.lines[view.scroll : view.scroll + per]
    _draw_text_lines(surface, font, [s[:110] for s in shown], 12, 36)
    _draw_bar(surface, font, view.message[:120] if view.message else "", h - 56)
    _draw_bar(surface, font, "Enter solve o open Esc back", h - 28)


def draw_lc_solve(surface: Any, font: Any, view: LcSolveState) -> None:
    """Draw editor text plus verdict panel."""
    import pygame

    from idle.gui import theme as theme_mod

    surface.fill(theme_mod.BG)
    w: int = surface.get_width()
    h: int = surface.get_height()
    _draw_bar(surface, font, f"Solve {view.slug} | Ctrl+T test Ctrl+S submit", 8)
    mid: int = h - 170
    area = pygame.Rect(8, 32, w - 16, mid - 40)
    view.editor.draw(surface, font, area)
    for idx, line in enumerate(view.panel.splitlines()[:6]):
        img = font.render(line[:110], True, theme_mod.FG)
        surface.blit(img, (12, mid + idx * font.get_linesize()))
    _draw_bar(surface, font, view.message[:120] if view.message else "", h - 28)


def draw_lc_login(surface: Any, font: Any, view: LcLoginState) -> None:
    """Draw username and password login form."""
    import pygame

    from idle.gui import theme as theme_mod

    surface.fill(theme_mod.BG)
    w: int = surface.get_width()
    _draw_bar(surface, font, "Login | Tab switch Enter save Esc back", 8)
    labels: list[str] = ["username", "password"]
    boxes: list[Textbox] = [view.username_box, view.password_box]
    for idx in range(2):
        y: int = 60 + idx * 80
        shown: str = boxes[idx].text if idx == 0 else "*" * len(boxes[idx].text)
        _draw_bar(surface, font, labels[idx], y)
        area = pygame.Rect(12, y + 22, w - 24, 40)
        color = theme_mod.ACCENT if view.focus == idx else theme_mod.DIM
        pygame.draw.rect(surface, color, area, 2 if view.focus == idx else 1)
        img = font.render(shown[-60:], True, theme_mod.FG)
        surface.blit(img, (18, y + 30))
    _draw_bar(surface, font, view.message[:120] if view.message else "", 240)


def _cycle_next(current: str | None, cycle: list[str | None]) -> str | None:
    """Return next value in cycle after current."""
    if current not in cycle:
        return cycle[0]
    idx: int = cycle.index(current)
    return cycle[(idx + 1) % len(cycle)]


def _handle_list_nav(event: Any, view: LcListState) -> str | None:
    """Handle Up Down Enter for list selection."""
    import pygame

    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        return None
    key: int = int(getattr(event, "key", 0))
    if key == pygame.K_UP:
        view.items.move(-1)
        return None
    if key == pygame.K_DOWN:
        view.items.move(1)
        return None
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return "open"
    return None


def _handle_list_shortcut(event: Any, view: LcListState) -> str | None:
    """Handle d s n g r keys for random single plus refresh."""
    import pygame

    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        return None
    key: int = int(getattr(event, "key", 0))
    if key == pygame.K_d:
        view.filters.difficulty = _cycle_next(view.filters.difficulty, DIFF_CYCLE)
        _rebuild_list_items(view)
        return None
    if key == pygame.K_s:
        view.filters.status = _cycle_next(view.filters.status, STATUS_CYCLE)
        _rebuild_list_items(view)
        return None
    if key == pygame.K_n:
        toggle_new_only(view)
        return None
    if key == pygame.K_g:
        return "random"
    if key == pygame.K_MINUS:
        view.filters.limit = max(LIMIT_MIN, view.filters.limit - LIMIT_STEP)
        _rebuild_list_items(view)
        return None
    if key in (pygame.K_EQUALS, pygame.K_PLUS):
        view.filters.limit = min(LIMIT_MAX, view.filters.limit + LIMIT_STEP)
        _rebuild_list_items(view)
        return None
    if key == pygame.K_r:
        return "refresh"
    if key == pygame.K_a:
        return "daily"
    return None


def handle_lc_list(event: Any, view: LcListState) -> str | None:
    """Handle list nav, filter keys, tag edit, Esc back.

    Test: d cycles difficulty, r returns refresh.
    """
    import pygame

    if view.tag_edit:
        if int(getattr(event, "type", -1)) == pygame.KEYDOWN and int(
            getattr(event, "key", 0)
        ) in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_ESCAPE):
            view.tag_edit = False
            view.filters.tag = view.tag_box.text.strip() or None
            _rebuild_list_items(view)
            return None
        view.tag_box.handle_key(event)
        return None
    if int(getattr(event, "type", -1)) == pygame.KEYDOWN:
        key: int = int(getattr(event, "key", 0))
        if key == pygame.K_ESCAPE:
            return "back"
        if key == pygame.K_t or key == pygame.K_SLASH:
            view.tag_edit = True
            return None
    nav: str | None = _handle_list_nav(event, view)
    if nav is not None:
        return nav
    return _handle_list_shortcut(event, view)


def handle_lc_detail(event: Any, view: LcDetailState) -> str | None:
    """Handle detail scroll, solve, open, back.

    Test: Down scrolls, Enter returns solve.
    """
    import pygame

    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        return None
    key: int = int(getattr(event, "key", 0))
    if key == pygame.K_ESCAPE:
        return "back"
    if key == pygame.K_UP:
        view.scroll = max(0, view.scroll - 1)
        return None
    if key == pygame.K_DOWN:
        view.scroll = min(max(0, len(view.lines) - 1), view.scroll + 1)
        return None
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return "solve"
    if key == pygame.K_o:
        return "open"
    return None


def _solve_shortcut(event: Any, view: LcSolveState) -> str | None:
    """Detect Ctrl+T test, Ctrl+S submit, Ctrl+O open."""
    import pygame

    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        return None
    key: int = int(getattr(event, "key", 0))
    mod: int = int(getattr(event, "mod", 0))
    if not bool(mod & pygame.KMOD_CTRL):
        return None
    if key == pygame.K_t:
        return "test"
    if key == pygame.K_s:
        return "submit"
    if key == pygame.K_o:
        return "open"
    return None


def handle_lc_solve(event: Any, view: LcSolveState) -> str | None:
    """Handle editor keys plus Test Submit Open shortcuts.

    Test: Ctrl+T returns test, Ctrl+S returns submit.
    """
    import pygame

    if int(getattr(event, "type", -1)) == pygame.KEYDOWN and int(
        getattr(event, "key", 0)
    ) == pygame.K_ESCAPE:
        return "back"
    hit: str | None = _solve_shortcut(event, view)
    if hit is not None:
        return hit
    view.editor.handle_key(event)
    return None


def _login_focused(view: LcLoginState) -> Textbox:
    """Return currently focused username or password box."""
    if view.focus == 1:
        return view.password_box
    return view.username_box


def handle_lc_login(event: Any, view: LcLoginState) -> str | None:
    """Handle login Tab switch, Enter save, Esc back.

    Test: empty session keeps form with cancel message.
    """
    import pygame

    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        _login_focused(view).handle_key(event)
        return None
    key: int = int(getattr(event, "key", 0))
    if key == pygame.K_ESCAPE:
        return "back"
    if key == pygame.K_TAB:
        view.focus = 1 if view.focus == 0 else 0
        return None
    if key == pygame.K_UP:
        view.focus = 0
        return None
    if key == pygame.K_DOWN:
        view.focus = 1
        return None
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        if view.focus == 0:
            view.focus = 1
            return None
        ok: bool
        msg: str
        ok, msg = try_login_password(
            view.username_box.text, view.password_box.text
        )
        view.message = msg
        view.saved = ok
        if ok:
            view.username_box = Textbox()
            view.password_box = Textbox()
            view.session_box = Textbox()
            view.csrf_box = Textbox()
            return "login_ok"
        return None
    _login_focused(view).handle_key(event)
    return None
