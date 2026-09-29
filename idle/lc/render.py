"""HTML to terminal text for problem statements."""

import html
import shutil
import textwrap
from html.parser import HTMLParser

_BLOCK_TAGS = ("p", "div", "ul", "ol", "h1", "h2", "h3", "h4")


class LCParser(HTMLParser):
    """Collect plain text with pre, list, and sup handling."""

    def __init__(self) -> None:
        """Init empty parts and flags."""
        super().__init__()
        self.parts: list[str] = []
        self._in_pre: bool = False
        self._in_sup: bool = False

    def handle_starttag(self, tag: str, attrs: object) -> None:
        """Emit markers for block and inline tags."""
        name: str = tag.lower()
        if name == "pre":
            self.parts.append("\n")
            self._in_pre = True
        elif name == "br":
            self.parts.append("\n")
        elif name == "li":
            self.parts.append("\n* ")
        elif name == "sup":
            self._in_sup = True
        elif name in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Close pre, sup, and block tags."""
        name: str = tag.lower()
        if name == "pre":
            self.parts.append("\n")
            self._in_pre = False
        elif name == "sup":
            self._in_sup = False
        elif name in _BLOCK_TAGS or name == "li":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        """Append text with pre indent and sup caret."""
        if not data:
            return
        if self._in_pre:
            lines: list[str] = data.splitlines()
            for i, line in enumerate(lines):
                if line.strip():
                    self.parts.append("    " + line.rstrip())
                if i < len(lines) - 1:
                    self.parts.append("\n")
            if data.endswith("\n"):
                self.parts.append("\n")
            return
        if self._in_sup:
            self.parts.append("^" + data.strip())
            return
        self.parts.append(data)

    def get_text(self) -> str:
        """Return joined collected parts."""
        return "".join(self.parts)


def _resolve_width(width: int) -> int:
    """Resolve width, falling back to terminal size."""
    if width and width > 0:
        return width
    try:
        return shutil.get_terminal_size().columns
    except OSError:
        return 80


def _collapse_blanks(lines: list[str]) -> list[str]:
    """Collapse runs of blanks to single blank."""
    out: list[str] = []
    blank: bool = False
    for line in lines:
        if not line.strip():
            if not blank:
                out.append("")
            blank = True
        else:
            out.append(line.rstrip())
            blank = False
    return out


def html_to_text(html_text: str, width: int = 80) -> str:
    """Convert problem HTML to wrapped plain text."""
    parser: LCParser = LCParser()
    parser.feed(html_text)
    raw: str = html.unescape(parser.get_text())
    size: int = _resolve_width(width)
    lines: list[str] = raw.splitlines()
    wrapped: list[str] = []
    for line in lines:
        if line.startswith("    "):
            wrapped.append(line.rstrip())
        elif not line.strip():
            wrapped.append("")
        else:
            chunk: str = " ".join(line.split())
            if len(chunk) <= size:
                wrapped.append(chunk)
            else:
                wrapped.extend(textwrap.fill(chunk, width=size).splitlines())
    clean: list[str] = _collapse_blanks(wrapped)
    while clean and not clean[0].strip():
        clean.pop(0)
    while clean and not clean[-1].strip():
        clean.pop()
    return "\n".join(clean)
