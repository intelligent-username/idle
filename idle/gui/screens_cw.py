"""Codewars pygame screens: list, detail, solve editor, login."""

from dataclasses import dataclass, field
import random
from typing import Any
import webbrowser

from idle.cw import api as cw_api
from idle.cw.auth import (
    load_saved_credentials,
    save_auth,
    validate_credentials,
)
from idle.cw.render import clean_markdown, format_kata_detail
from idle.cw.scaffold import scaffold_kata, strip_header
from idle.gui.widgets import Textbox

__all__: list[str] = [
    "CwDetailState",
    "CwFilterState",
    "CwListState",
    "CwLoginState",
    "CwSolveState",
    "draw_cw_detail",
    "draw_cw_list",
    "draw_cw_login",
    "draw_cw_solve",
    "handle_cw_detail",
    "handle_cw_list",
    "handle_cw_login",
    "handle_cw_solve",
    "make_cw_detail_state",
    "make_cw_login_state",
]

RANK_COLORS: dict[str, tuple[int, int, int]] = {
    "white": (240, 240, 240),
    "yellow": (236, 178, 46),
    "blue": (60, 153, 220),
    "purple": (134, 101, 196),
}


@dataclass
class CwFilterState:
    """Filter criteria for kata list."""

    rank: str | None = None
    tag: str | None = None
    status: str | None = None


@dataclass
class CwListState:
    """Catalog view state with current selection."""

    filters: CwFilterState = field(default_factory=CwFilterState)
    current: dict[str, Any] | None = None
    tag_edit: bool = False
    new_only: bool = False
    message: str = ""
    needs_login: bool = False


@dataclass
class CwDetailState:
    """Kata detail viewer with scrolling lines."""

    slug: str = ""
    detail: dict[str, Any] | None = None
    text: str = ""
    lines: list[str] = field(default_factory=list)
    scroll: int = 0
    message: str = ""


@dataclass
class CwSolveState:
    """Editor and test execution state."""

    slug: str = ""
    editor: Textbox = field(default_factory=lambda: Textbox(multiline=True))
    panel: str = ""
    message: str = ""


@dataclass
class CwLoginState:
    """Codewars login form for username and optional API key."""

    username_box: Textbox = field(default_factory=Textbox)
    api_key_box: Textbox = field(default_factory=Textbox)
    focus: int = 0
    message: str = ""
    saved: bool = False


def _draw_bar(surface: Any, font: Any, text: str, y: int) -> None:
    """Draw single bar line."""
    from idle.gui import theme as theme_mod

    img = font.render(text[:120], True, theme_mod.DIM)
    surface.blit(img, (12, y))


def _draw_text_lines(surface: Any, font: Any, lines: list[str], x: int, y: int) -> int:
    """Draw lines top to bottom."""
    from idle.gui import theme as theme_mod

    cur: int = y
    for line in lines:
        img = font.render(line, True, theme_mod.FG)
        surface.blit(img, (x, cur))
        cur += font.get_linesize()
    return cur


def load_kata_list(username: str = "", refresh: bool = False) -> tuple[list[dict[str, Any]], str, bool]:
    """Fetch kata list with offline fallback."""
    try:
        katas = cw_api.fetch_kata_list(username=username, refresh=refresh)
        return katas, "", False
    except (OSError, RuntimeError) as exc:
        return cw_api.CURATED_KATAS, f"Using offline catalog ({exc})", False


def pick_random_kata(katas: list[dict[str, Any]], filters: CwFilterState, new_only: bool) -> dict[str, Any] | None:
    """Filter and pick random kata."""
    candidates = []
    for k in katas:
        r_name = (k.get("rank") or {}).get("name", "").lower()
        if filters.rank and filters.rank.lower() not in r_name:
            continue
        if filters.tag:
            k_tags = [t.lower() for t in k.get("tags", [])]
            if filters.tag.lower() not in k_tags:
                continue
        if new_only and k.get("status") == "ac":
            continue
        candidates.append(k)
    return random.choice(candidates) if candidates else None


def draw_cw_list(surface: Any, font: Any, view: CwListState) -> None:
    """Draw Codewars catalog/random picker screen."""
    import pygame
    from idle.gui import theme as theme_mod

    surface.fill(theme_mod.BG)
    w: int = surface.get_width()
    h: int = surface.get_height()

    filt_str = f"rank:{view.filters.rank or 'All'} tag:{view.filters.tag or 'All'}"
    _draw_bar(surface, font, f"Codewars Katas | {filt_str}", 8)

    check: str = "[x]" if view.new_only else "[ ]"
    _draw_bar(surface, font, f"{check} unsolved only (n to toggle)", 30)

    if view.current is None:
        _draw_bar(surface, font, "No katas match filters. Press 'g' to retry or 'r' to refresh.", 58)
    else:
        row = pygame.Rect(8, 56, w - 16, font.get_linesize() + 6)
        surface.fill(theme_mod.DIM, row)
        rank_obj = view.current.get("rank") or {}
        r_name = rank_obj.get("name", "N/A")
        name = str(view.current.get("name", ""))[:40]
        stat = "SOLVED" if view.current.get("status") == "ac" else "TODO"
        line = f"{r_name:>8}  {name:<40}  {stat}"
        img = font.render(line, True, theme_mod.FG)
        surface.blit(img, (12, 58))

        tags = ", ".join(view.current.get("tags", [])[:3])
        _draw_bar(surface, font, f"Tags: {tags or 'None'}", 86)

    _draw_bar(surface, font, view.message[:120] if view.message else "", h - 56)
    _draw_bar(surface, font, "g random | n unsolved-only | d rank | r refresh | Enter solve | Esc menu", h - 28)


def handle_cw_list(event: Any, view: CwListState, all_katas: list[dict[str, Any]]) -> str | None:
    """Handle navigation and shortcuts on kata list screen."""
    import pygame

    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        return None
    key: int = int(getattr(event, "key", 0))

    if key == pygame.K_ESCAPE:
        return "menu"
    if key == pygame.K_g:
        view.current = pick_random_kata(all_katas, view.filters, view.new_only)
        return None
    if key == pygame.K_n:
        view.new_only = not view.new_only
        view.current = pick_random_kata(all_katas, view.filters, view.new_only)
        return None
    if key == pygame.K_d:
        ranks = [None, "8 kyu", "7 kyu", "6 kyu", "5 kyu", "4 kyu", "3 kyu"]
        cur_idx = ranks.index(view.filters.rank) if view.filters.rank in ranks else 0
        view.filters.rank = ranks[(cur_idx + 1) % len(ranks)]
        view.current = pick_random_kata(all_katas, view.filters, view.new_only)
        return None
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        if view.current:
            return "detail"
        return None
    return None


def make_cw_detail_state(detail: dict[str, Any] | None, text: str, slug: str) -> CwDetailState:
    """Build detail state with wrapped lines."""
    lines: list[str] = text.splitlines() if text else []
    return CwDetailState(slug=slug, detail=detail, text=text, lines=lines)


def draw_cw_detail(surface: Any, font: Any, view: CwDetailState) -> None:
    """Draw scrollable kata detail screen."""
    from idle.gui import theme as theme_mod

    surface.fill(theme_mod.BG)
    h: int = surface.get_height()
    _draw_bar(surface, font, f"Kata: {view.slug} | Up/Down to scroll", 8)

    per: int = max(1, (h - 80) // max(1, font.get_linesize()))
    shown: list[str] = view.lines[view.scroll : view.scroll + per]
    _draw_text_lines(surface, font, [s[:110] for s in shown], 12, 36)

    _draw_bar(surface, font, view.message[:120] if view.message else "", h - 56)
    _draw_bar(surface, font, "Enter solve | o open in browser | Esc back", h - 28)


def handle_cw_detail(event: Any, view: CwDetailState) -> str | None:
    """Handle detail screen keys."""
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
        url = f"https://www.codewars.com/kata/{view.slug}"
        webbrowser.open(url)
        return None
    return None


def draw_cw_solve(surface: Any, font: Any, view: CwSolveState) -> None:
    """Draw solution editor with test verdict panel."""
    import pygame
    from idle.gui import theme as theme_mod

    surface.fill(theme_mod.BG)
    w: int = surface.get_width()
    h: int = surface.get_height()

    _draw_bar(surface, font, f"Solve {view.slug} | Ctrl+T test | Esc back", 8)
    mid: int = h - 170
    area = pygame.Rect(8, 32, w - 16, mid - 40)
    view.editor.draw(surface, font, area)

    for idx, line in enumerate(view.panel.splitlines()[:6]):
        img = font.render(line[:110], True, theme_mod.FG)
        surface.blit(img, (12, mid + idx * font.get_linesize()))

    _draw_bar(surface, font, view.message[:120] if view.message else "", h - 28)


def handle_cw_solve(event: Any, view: CwSolveState) -> str | None:
    """Handle solve screen keys."""
    import pygame

    if int(getattr(event, "type", -1)) == pygame.KEYDOWN:
        key: int = int(getattr(event, "key", 0))
        mod: int = int(getattr(event, "mod", 0))
        if key == pygame.K_ESCAPE:
            return "back"
        if key == pygame.K_t and bool(mod & pygame.KMOD_CTRL):
            # Run code locally
            code_text = view.editor.text
            try:
                scope: dict[str, Any] = {}
                exec(code_text, scope)
                view.panel = "Local execution: SUCCESS (no exceptions)"
            except Exception as exc:
                view.panel = f"Local execution: FAILED\n{type(exc).__name__}: {exc}"
            return None

    view.editor.handle_key(event)
    return None


def make_cw_login_state() -> CwLoginState:
    """Create login state with prefilled credentials from .env or auth.json."""
    saved_key, saved_user = load_saved_credentials()
    state = CwLoginState()
    if saved_user:
        state.username_box.text = saved_user
    if saved_key:
        state.api_key_box.text = saved_key
    return state


def draw_cw_login(surface: Any, font: Any, view: CwLoginState) -> None:
    """Draw Codewars credentials screen."""
    import pygame
    from idle.gui import theme as theme_mod

    surface.fill(theme_mod.BG)
    _draw_bar(surface, font, "Codewars Authentication Setup (No CAPTCHA)", 8)

    _draw_bar(surface, font, "Username:", 48)
    u_rect = pygame.Rect(12, 70, 350, 28)
    view.username_box.draw(surface, font, u_rect, active=(view.focus == 0))

    _draw_bar(surface, font, "API Access Token (optional, from Account Settings):", 112)
    k_rect = pygame.Rect(12, 134, 350, 28)
    view.api_key_box.draw(surface, font, k_rect, active=(view.focus == 1))

    if view.message:
        color = theme_mod.CORRECT if view.saved else theme_mod.WRONG
        img = font.render(view.message[:110], True, color)
        surface.blit(img, (12, 180))

    _draw_bar(surface, font, "Tab switch field | Enter save & validate | Esc back", surface.get_height() - 28)


def handle_cw_login(event: Any, view: CwLoginState) -> str | None:
    """Handle Codewars login screen interaction."""
    import pygame

    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        active_box = view.username_box if view.focus == 0 else view.api_key_box
        active_box.handle_key(event)
        return None

    key: int = int(getattr(event, "key", 0))
    if key == pygame.K_ESCAPE:
        return "back"
    if key == pygame.K_TAB or key in (pygame.K_UP, pygame.K_DOWN):
        view.focus = 1 if view.focus == 0 else 0
        return None
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        if view.focus == 0 and not view.username_box.text.strip():
            view.message = "Username cannot be empty."
            return None
        ok, msg = validate_credentials(api_key=view.api_key_box.text.strip(), username=view.username_box.text.strip())
        view.saved = ok
        view.message = msg
        if ok:
            save_auth(api_key=view.api_key_box.text.strip(), username=view.username_box.text.strip())
            return "login_ok"
        return None

    active_box = view.username_box if view.focus == 0 else view.api_key_box
    active_box.handle_key(event)
    return None
