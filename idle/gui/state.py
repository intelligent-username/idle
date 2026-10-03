"""GUI navigation state (no pygame dependency)."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Screen(Enum):
    """GUI screens reachable from the menu."""

    MENU = "menu"
    TYPE = "type"
    DRILL = "drill"
    LC_LIST = "lc_list"
    LC_DETAIL = "lc_detail"
    LC_SOLVE = "lc_solve"
    STATS = "stats"
    CONFIG = "config"


@dataclass
class AppState:
    """Mutable GUI state plus screen stack."""

    screen: Screen = Screen.MENU
    stack: list[Screen] = field(default_factory=list)
    db_path: str = ""
    config: dict[str, Any] = field(default_factory=dict)
    text: str = ""
    session: Any = None
    result: Any = None
    problem: Any = None
    detail: str = ""
    code: str = ""
    filter: str = ""
    limit: int = 50
    message: str = ""
    typing_difficulty: int = 0
    drill_difficulty: int = 0

    def push(self, screen: Screen) -> None:
        """Push current screen and switch to given one."""
        self.stack.append(self.screen)
        self.screen = screen

    def pop(self) -> Screen:
        """Return to previous screen, stay if stack empty."""
        if self.stack:
            self.screen = self.stack.pop()
        return self.screen
