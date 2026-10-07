"""Scaffold solution files and strip header helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def strip_header(code: str) -> str:
    """Strip comment header lines from solution code."""
    lines = code.splitlines(keepends=True)
    start = 0
    while start < len(lines) and (lines[start].strip().startswith("#") or not lines[start].strip()):
        start += 1
    return "".join(lines[start:])


def scaffold_problem(detail: dict[str, Any], lang: str = "python3", workdir: str | Path | None = None) -> Path:
    """Scaffold a solution.py file and test.txt file in workdir."""
    target_dir = Path(workdir) if workdir else Path.cwd()
    target_dir.mkdir(parents=True, exist_ok=True)

    title = detail.get("title", "Untitled Problem")
    slug = detail.get("slug", "problem")
    snippets = detail.get("code_snippets", {})
    snippet = snippets.get(lang) or snippets.get("python3") or "class Solution:\n    pass\n"

    header = f"# {title}\n# Slug: {slug}\n\n"
    sol_file = target_dir / "solution.py"
    sol_file.write_text(header + snippet, encoding="utf-8")

    sample_test = detail.get("sample_test_case", "")
    test_file = target_dir / "test.txt"
    test_file.write_text(sample_test, encoding="utf-8")

    return sol_file
