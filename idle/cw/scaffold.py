"""Scaffold solution files for Codewars katas."""

from pathlib import Path
import re
from typing import Any


def strip_header(code: str) -> str:
    """Strip leading comment header lines."""
    lines: list[str] = code.splitlines()
    cut: int = 0
    for line in lines:
        if line.lstrip().startswith("#"):
            cut += 1
        elif not line.strip() and cut > 0:
            cut += 1
            break
        else:
            break
    rest: list[str] = lines[cut:]
    while rest and not rest[0].strip():
        rest.pop(0)
    text: str = "\n".join(rest)
    return text + "\n" if text else ""


def _resolve_workdir(explicit: str | None = None) -> Path:
    """Resolve workdir from argument, config, or cwd."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    from idle.config import load_config

    cfg: dict[str, Any] = load_config()
    cw_dir = cfg.get("cw_workdir") or cfg.get("codewars_workdir") or cfg.get("workdir")
    if cw_dir:
        return Path(str(cw_dir)).expanduser().resolve()
    return Path.cwd()


def _sanitize_slug(slug: str) -> str:
    """Sanitize slug for safe filename."""
    clean = re.sub(r"[^\w\-]", "_", slug)
    return clean.replace("-", "_")


def scaffold_kata(kata: dict[str, Any], workdir: str | None = None) -> Path:
    """Generate solution file with instructions and starter stub."""
    target_dir: Path = _resolve_workdir(workdir)
    target_dir.mkdir(parents=True, exist_ok=True)

    slug: str = kata.get("slug") or kata.get("id") or "kata"
    filename: str = f"cw_{_sanitize_slug(slug)}.py"
    target_file: Path = target_dir / filename

    if target_file.exists():
        return target_file

    name: str = kata.get("name", "Untitled")
    rank_obj: dict[str, Any] = kata.get("rank") or {}
    rank_name: str = rank_obj.get("name", "unknown")
    url: str = kata.get("url") or f"https://www.codewars.com/kata/{slug}"

    func_name: str = _sanitize_slug(slug)
    if func_name.startswith("cw_"):
        func_name = func_name[3:]

    content = f'''# Codewars: {name} [{rank_name}]
# URL: {url}
#
# Instructions:
# Implement your solution below. You can run tests locally with:
# idle cw test {slug}

def solution(*args, **kwargs):
    """Implement solution for {name}."""
    pass

# Simple test runner
if __name__ == "__main__":
    print("Testing solution...")
    # Add your test cases below, e.g.:
    # assert solution() == expected
    print("All local tests passed!")
'''
    target_file.write_text(content, encoding="utf-8")
    return target_file
