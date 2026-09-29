"""Reusable pygame widgets (lazy pygame, headless-safe)."""

from typing import Any

from idle.gui import theme

__all__: list[str] = ["Textbox", "ScrollableList", "Button"]

BLINK_PERIOD_MS: int = 530
PAD: int = 6


class Textbox:
    """Single or multiline text input with caret and blink."""

    def __init__(self, multiline: bool = False, text: str = "") -> None:
        """Store mode and text, place caret at end."""
        self.multiline: bool = multiline
        self.text: str = text
        self.caret: int = len(text)
        self.confirmed: bool = False
        self.blink_on: bool = True
        self._blink_ms: int = 0

    def _insert(self, chunk: str) -> None:
        """Insert chunk at caret and advance caret."""
        if not chunk:
            return
        self.text = self.text[: self.caret] + chunk + self.text[self.caret :]
        self.caret += len(chunk)
        self._reset_blink()

    def _backspace(self) -> None:
        """Delete one char before caret."""
        if self.caret <= 0:
            return
        self.text = self.text[: self.caret - 1] + self.text[self.caret :]
        self.caret -= 1
        self._reset_blink()

    def _delete_word(self) -> None:
        """Delete word backwards (Ctrl+W)."""
        if self.caret <= 0:
            return
        end: int = self.caret
        start: int = end
        while start > 0 and self.text[start - 1] == " ":
            start -= 1
        while start > 0 and self.text[start - 1] not in (" ", "\n"):
            start -= 1
        self.text = self.text[:start] + self.text[end:]
        self.caret = start
        self._reset_blink()

    def _reset_blink(self) -> None:
        """Make caret visible and restart blink timer."""
        self.blink_on = True
        self._blink_ms = 0

    def _handle_return(self) -> None:
        """Insert newline if multiline else flag confirm."""
        if self.multiline:
            self._insert("\n")
        else:
            self.confirmed = True

    def _handle_nav(self, key: int) -> bool:
        """Move caret for Left/Right/Home/End. Return True if handled."""
        import pygame

        if key == pygame.K_LEFT:
            self.caret = max(0, self.caret - 1)
        elif key == pygame.K_RIGHT:
            self.caret = min(len(self.text), self.caret + 1)
        elif key == pygame.K_HOME:
            self.caret = self._line_start()
        elif key == pygame.K_END:
            self.caret = self._line_end()
        else:
            return False
        self._reset_blink()
        return True

    def _line_start(self) -> int:
        """Return offset of current line start."""
        idx: int = self.text.rfind("\n", 0, self.caret)
        return idx + 1

    def _line_end(self) -> int:
        """Return offset of current line end."""
        idx: int = self.text.find("\n", self.caret)
        return len(self.text) if idx == -1 else idx

    def handle_key(self, event: Any) -> None:
        """Handle TEXTINPUT, BACKSPACE, Ctrl+W, RETURN, arrows."""
        import pygame

        etype: int = int(getattr(event, "type", -1))
        if etype == pygame.TEXTINPUT:
            self._insert(str(getattr(event, "text", "")))
            return
        if etype != pygame.KEYDOWN:
            return
        key: int = int(getattr(event, "key", 0))
        mod: int = int(getattr(event, "mod", 0))
        ctrl: bool = bool(mod & pygame.KMOD_CTRL)
        if ctrl and key == pygame.K_w:
            self._delete_word()
            return
        if key == pygame.K_BACKSPACE:
            if ctrl:
                self._delete_word()
            else:
                self._backspace()
            return
        if key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._handle_return()
            return
        self._handle_nav(key)

    def update(self, dt_ms: int) -> None:
        """Advance caret blink timer by dt_ms."""
        self._blink_ms += dt_ms
        if self._blink_ms >= BLINK_PERIOD_MS:
            self._blink_ms = 0
            self.blink_on = not self.blink_on

    def draw(self, surface: Any, font: Any, rect: Any) -> None:
        """Draw box, visible text, and blinking caret."""
        import pygame

        from idle.gui import theme as theme_mod

        area = pygame.Rect(rect)
        surface.fill(theme_mod.BG, area)
        pygame.draw.rect(surface, theme_mod.DIM, area, 1)
        x: int = area.x + PAD
        y: int = area.y + PAD
        for line in self.text.split("\n"):
            img = font.render(line, True, theme_mod.FG)
            surface.blit(img, (x, y))
            y += font.get_linesize()
        if self.blink_on:
            cx: int = x + font.size(self.text[: self.caret].split("\n")[-1])[0]
            cy: int = y - font.get_linesize()
            pygame.draw.line(surface, theme_mod.FG, (cx, cy), (cx, cy + font.get_linesize()), 1)


class ScrollableList:
    """Vertical selectable list with scroll window."""

    def __init__(
        self, items: list[str], selected: int = 0, visible_count: int = 12
    ) -> None:
        """Store items, clamp selection, init scroll offset."""
        self.items: list[str] = list(items)
        self.selected: int = 0
        self.offset: int = 0
        self.visible_count: int = max(1, visible_count)
        if self.items:
            self.selected = max(0, min(selected, len(self.items) - 1))
        self.ensure_visible()

    def move(self, delta: int) -> None:
        """Move selection by delta, clamped, keep visible."""
        if not self.items:
            return
        self.selected = max(0, min(len(self.items) - 1, self.selected + delta))
        self.ensure_visible()

    def ensure_visible(self) -> None:
        """Shift offset so selection stays in visible window."""
        if not self.items:
            self.offset = 0
            return
        self.offset = max(0, min(self.offset, max(0, len(self.items) - 1)))
        if self.selected < self.offset:
            self.offset = self.selected
        elif self.selected >= self.offset + self.visible_count:
            self.offset = self.selected - self.visible_count + 1

    def selected_item(self) -> str | None:
        """Return selected item or None when empty."""
        if not self.items:
            return None
        return self.items[self.selected]

    def handle_key(self, event: Any) -> str | None:
        """Handle Up/Down arrows and Return. Return confirm or None."""
        import pygame

        if int(getattr(event, "type", -1)) != pygame.KEYDOWN:
            return None
        key: int = int(getattr(event, "key", 0))
        if key == pygame.K_UP:
            self.move(-1)
        elif key == pygame.K_DOWN:
            self.move(1)
        elif key in (pygame.K_RETURN, pygame.K_KP_ENTER):
            return "confirm"
        return None

    def draw(self, surface: Any, font: Any, rect: Any) -> None:
        """Draw visible slice, highlight selected row."""
        import pygame

        area = pygame.Rect(rect)
        surface.fill(theme.BG, area)
        row_h: int = font.get_linesize() + 2
        end: int = min(len(self.items), self.offset + self.visible_count)
        for i in range(self.offset, end):
            y: int = area.y + (i - self.offset) * row_h
            row = pygame.Rect(area.x, y, area.w, row_h)
            if i == self.selected:
                surface.fill(theme.DIM, row)
            img = font.render(self.items[i], True, theme.FG)
            surface.blit(img, (area.x + PAD, y))


class Button:
    """Labeled button with keyboard focus ring."""

    def __init__(self, label: str, focused: bool = False) -> None:
        """Store label and focus flag."""
        self.label: str = label
        self.focused: bool = focused

    def draw(self, surface: Any, font: Any, rect: Any) -> None:
        """Draw label centered, ACCENT ring when focused."""
        import pygame

        area = pygame.Rect(rect)
        surface.fill(theme.BG, area)
        border = theme.ACCENT if self.focused else theme.DIM
        width: int = 2 if self.focused else 1
        pygame.draw.rect(surface, border, area, width)
        img = font.render(self.label, True, theme.FG)
        ix: int = area.x + max(0, (area.w - img.get_width()) // 2)
        iy: int = area.y + max(0, (area.h - img.get_height()) // 2)
        surface.blit(img, (ix, iy))
