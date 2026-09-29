"""Theme tokens for pygame GUI (no pygame import at top level)."""

from typing import Any

BG: tuple[int, int, int] = (10, 10, 12)
FG: tuple[int, int, int] = (229, 231, 235)
CORRECT: tuple[int, int, int] = (74, 222, 128)
WRONG: tuple[int, int, int] = (248, 113, 113)
DIM: tuple[int, int, int] = (107, 114, 128)
ACCENT: tuple[int, int, int] = (96, 165, 250)
LOGICAL_W: int = 960
LOGICAL_H: int = 640
FPS: int = 60
FONT_SPEC: str = "consolas,menlo,monospace"
KEYBINDS: dict[str, str] = {
    "back": "Esc",
    "restart": "Tab",
    "confirm": "Enter",
    "navigate": "Up/Down/Left/Right",
    "delete_word": "Ctrl+W",
    "test": "Ctrl+T",
    "submit": "Ctrl+S",
    "open": "Ctrl+O",
}


def get_font(size: int) -> Any:
    """Return system monospace font at given size."""
    import pygame

    return pygame.font.SysFont(FONT_SPEC, size)
