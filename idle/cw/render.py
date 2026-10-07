"""Markdown and text rendering for Codewars katas."""

import re
import shutil
import textwrap
from typing import Any


def clean_markdown(text: str) -> str:
    """Format markdown text cleanly for terminal display."""
    if not text:
        return ""

    # Replace markdown links [text](url) -> text (url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", text)

    # Convert headers # Title -> TITLE
    text = re.sub(r"^#{1,6}\s*(.+)$", lambda m: f"\n=== {m.group(1).strip()} ===\n", text, flags=re.MULTILINE)

    # Clean backticks `code` -> `code`
    lines: list[str] = []
    width: int = min(shutil.get_terminal_size((80, 24)).columns, 100)
    in_code_block: bool = False

    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            lines.append("    " + line.strip())
            continue
        if in_code_block:
            lines.append("    " + line)
        elif not line.strip():
            lines.append("")
        elif line.strip().startswith(("-", "*", "•")):
            wrapped = textwrap.fill(line.strip(), width=width, initial_indent="  ", subsequent_indent="    ")
            lines.append(wrapped)
        else:
            wrapped = textwrap.fill(line.strip(), width=width)
            lines.append(wrapped)

    return "\n".join(lines).strip()


def format_kata_detail(kata: dict[str, Any]) -> str:
    """Render full kata detail text."""
    name: str = kata.get("name", "Untitled")
    rank_obj: dict[str, Any] = kata.get("rank") or {}
    rank_name: str = rank_obj.get("name", "Unknown rank")
    slug: str = kata.get("slug", "")
    url: str = kata.get("url", f"https://www.codewars.com/kata/{slug}")
    tags: list[str] = kata.get("tags", [])
    author_obj: dict[str, Any] = kata.get("createdBy") or {}
    author: str = author_obj.get("username", "Unknown")

    header: list[str] = [
        f"KATA: {name} [{rank_name}]",
        f"Slug: {slug}",
        f"Tags: {', '.join(tags) if tags else 'None'}",
        f"Author: {author}",
        f"URL: {url}",
        "-" * 60,
        "",
    ]

    desc: str = clean_markdown(kata.get("description", "No description available."))
    return "\n".join(header) + desc + "\n"
