"""Menu screen with Best header and keyboard nav."""

from pathlib import Path
from typing import Any

from idle.gui.state import Screen

__all__: list[str] = [
    "DIFFICULTIES",
    "DIFFICULTY_COLORS",
    "MENU_LABELS",
    "format_header",
    "get_best_value",
    "get_solved_count",
    "load_header",
    "menu_target",
    "handle_menu",
    "draw_menu",
]

DIFFICULTIES: list[str] = [
    "Easy",
    "Medium",
    "Hard",
    "Expert",
    "Master",
]

DIFFICULTY_COLORS: list[tuple[int, int, int]] = [
    (74, 222, 128),  # Green (theme.CORRECT)
    (96, 165, 250),  # Cyan / Blue (theme.ACCENT)
    (251, 191, 36),  # Amber / Yellow
    (251, 146, 60),  # Orange
    (248, 113, 113),  # Red (theme.WRONG)
]

MENU_LABELS: list[str] = [
    "1) type",
    "2) drill",
    "3) leetcode",
    "4) stats",
    "5) config",
    "6) quit",
]

FOOTER_HINT: str = "Up/Down select, Left/Right diff, Enter/1-6 start, Esc quit"


def get_best_value(conn: Any) -> float | None:
    """Return max net WPM or None when empty."""
    from idle.db import get_best

    return get_best(conn)


def get_solved_count(conn: Any) -> int:
    """Return count of solved LC problems."""
    from idle.db import get_header_stats

    _, solved = get_header_stats(conn)
    return solved


def format_header(best: float | None, solved: int) -> str:
    """Format Best and Solved one-liner."""
    best_txt: str = f"{best:.1f} WPM" if best is not None else "--"
    return f"Best: {best_txt} | Solved: {solved}"


def load_header(db_path: str | Path) -> str:
    """Load header text from DB path, friendly on empty or error."""
    from idle.db import get_db
    from idle.db import get_header_stats

    try:
        conn = get_db(Path(db_path))
    except OSError:
        return format_header(None, 0)
    try:
        best, solved = get_header_stats(conn)
        return format_header(best, solved)
    finally:
        conn.close()


def menu_target(index: int) -> Screen | None:
    """Map menu index to Screen, None means quit."""
    if index == 0:
        return Screen.TYPE
    if index == 1:
        return Screen.DRILL
    if index == 2:
        return Screen.LC_LIST
    if index == 3:
        return Screen.STATS
    if index == 4:
        return Screen.CONFIG
    return None


def _number_index(key: int) -> int | None:
    """Map pygame number key to menu index or None."""
    import pygame

    nums: dict[int, int] = {
        pygame.K_1: 0,
        pygame.K_2: 1,
        pygame.K_3: 2,
        pygame.K_4: 3,
        pygame.K_5: 4,
        pygame.K_6: 5,
        pygame.K_KP1: 0,
        pygame.K_KP2: 1,
        pygame.K_KP3: 2,
        pygame.K_KP4: 3,
        pygame.K_KP5: 4,
        pygame.K_KP6: 5,
    }
    return nums.get(key)


def _activate(index: int) -> tuple[int, Screen | None, bool]:
    """Activate index, quit flag True only for quit row."""
    if index == len(MENU_LABELS) - 1:
        return (index, None, True)
    return (index, menu_target(index), False)


def handle_menu(
    event: Any, selected: int, state: Any = None
) -> tuple[int, Screen | None, bool]:
    """Handle arrows, numbers, Enter, Esc for menu."""
    import pygame

    count: int = len(MENU_LABELS)
    cur: int = max(0, min(selected, count - 1))
    if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
        return (cur, None, False)
    key: int = int(getattr(event, "key", 0))
    if key == pygame.K_ESCAPE:
        return (cur, None, True)
    if key == pygame.K_UP:
        return ((cur - 1) % count, None, False)
    if key == pygame.K_DOWN:
        return ((cur + 1) % count, None, False)
    if key == pygame.K_LEFT:
        if cur == 0 and state is not None:
            state.typing_difficulty = (
                getattr(state, "typing_difficulty", 0) - 1
            ) % len(DIFFICULTIES)
        elif cur == 1 and state is not None:
            state.drill_difficulty = (
                getattr(state, "drill_difficulty", 0) - 1
            ) % len(DIFFICULTIES)
        return (cur, None, False)
    if key == pygame.K_RIGHT:
        if cur == 0 and state is not None:
            state.typing_difficulty = (
                getattr(state, "typing_difficulty", 0) + 1
            ) % len(DIFFICULTIES)
        elif cur == 1 and state is not None:
            state.drill_difficulty = (
                getattr(state, "drill_difficulty", 0) + 1
            ) % len(DIFFICULTIES)
        return (cur, None, False)
    if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
        return _activate(cur)
    num: int | None = _number_index(key)
    if num is not None:
        return _activate(num)
    return (cur, None, False)


def _menu_lines(header: str, message: str) -> list[str]:
    """Build header, items, and footer lines."""
    lines: list[str] = [header, ""]
    lines.extend(MENU_LABELS)
    lines.append("")
    lines.append(message if message else FOOTER_HINT)
    return lines


def draw_menu(surface: Any, state: Any, selected: int, header: str) -> None:
    """Draw header plus selectable menu items."""
    import pygame

    from idle.gui import theme

    font: Any = theme.get_font(20)
    row_h: int = font.get_linesize() + 4
    surface.fill(theme.BG)
    msg: str = str(getattr(state, "message", "") or "")
    lines: list[str] = _menu_lines(header, msg)
    y: int = 24
    for pos, line in enumerate(lines):
        img: Any = font.render(line, True, theme.FG)
        surface.blit(img, (24, y))
        idx: int = pos - 2
        if 0 <= idx < len(MENU_LABELS):
            if idx == 0:
                diff_idx: int = (
                    getattr(state, "typing_difficulty", 0) % len(DIFFICULTIES)
                )
                diff_name: str = DIFFICULTIES[diff_idx]
                diff_color: tuple[int, int, int] = DIFFICULTY_COLORS[diff_idx]
                centered: str = diff_name.center(6)
                diff_text: str = (
                    f"< {centered} >" if idx == selected else f"  {centered}  "
                )
                diff_img: Any = font.render(diff_text, True, diff_color)
                surface.blit(diff_img, (220, y))
            elif idx == 1:
                diff_idx = (
                    getattr(state, "drill_difficulty", 0) % len(DIFFICULTIES)
                )
                diff_name = DIFFICULTIES[diff_idx]
                diff_color = DIFFICULTY_COLORS[diff_idx]
                centered = diff_name.center(6)
                diff_text = (
                    f"< {centered} >" if idx == selected else f"  {centered}  "
                )
                diff_img = font.render(diff_text, True, diff_color)
                surface.blit(diff_img, (220, y))

            if idx == selected:
                w: int = img.get_width() + 16
                pygame.draw.rect(surface, theme.ACCENT, (16, y - 2, w, row_h), 1)
        y += row_h
