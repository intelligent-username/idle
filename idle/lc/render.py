"""HTML to text renderer for LeetCode descriptions."""

from __future__ import annotations

import html
import re
import textwrap


def html_to_text(html_str: str, width: int = 80) -> str:
    """Convert HTML string to formatted plain text."""
    if not html_str:
        return ""

    s = re.sub(r"<sup>(.*?)</sup>", r"^\1", html_str, flags=re.DOTALL)
    s = re.sub(r"<li>(.*?)</li>", r"* \1\n", s, flags=re.DOTALL)

    def _pre_sub(m: re.Match[str]) -> str:
        content = m.group(1)
        indented = "\n".join("    " + line for line in content.splitlines())
        return "\n" + indented + "\n"

    s = re.sub(r"<pre>(.*?)</pre>", _pre_sub, s, flags=re.DOTALL)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)

    lines: list[str] = []
    for line in s.splitlines():
        if line.startswith("    "):
            lines.append(line)
        elif line.strip().startswith("* "):
            lines.append(textwrap.fill(line.strip(), width=width, initial_indent="", subsequent_indent="  "))
        elif line.strip():
            lines.append(textwrap.fill(line.strip(), width=width))

    return "\n".join(lines)
