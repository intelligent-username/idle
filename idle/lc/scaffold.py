"""Scaffold solution files for LeetCode problems."""

from pathlib import Path
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


def _pick_snippet(detail: dict[str, Any], lang: str) -> str:
    """Pick code snippet for lang, python3 only path."""
    raw: Any = detail.get("code_snippets")
    if isinstance(raw, dict):
        if lang in raw and isinstance(raw[lang], str):
            return str(raw[lang])
        if "python3" in raw and isinstance(raw["python3"], str):
            return str(raw["python3"])
        for value in raw.values():
            if isinstance(value, str) and value.strip():
                return value
        return ""
    snaps: Any = detail.get("codeSnippets")
    if isinstance(snaps, list):
        for entry in snaps:
            if isinstance(entry, dict) and entry.get("langSlug") == lang:
                return str(entry.get("code") or "")
    return ""


def _detail_str(detail: dict[str, Any], *keys: str) -> str:
    """Return first non-empty string for keys."""
    for key in keys:
        value: Any = detail.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def _tag_list(detail: dict[str, Any]) -> list[str]:
    """Extract tag slugs as string list."""
    tags: Any = detail.get("tags")
    if isinstance(tags, list):
        return [str(t) for t in tags if str(t).strip()]
    raw: Any = detail.get("topicTags")
    out: list[str] = []
    if isinstance(raw, list):
        for entry in raw:
            if isinstance(entry, dict) and entry.get("slug"):
                out.append(str(entry["slug"]))
    return out


def _resolve_workdir(explicit: str | None) -> Path:
    """Resolve workdir from arg or config."""
    if explicit:
        return Path(explicit).expanduser()
    from idle.config import load_config

    cfg: dict[str, Any] = load_config()
    lc: Any = cfg.get("lc", {})
    raw: str = "~/leetcode"
    if isinstance(lc, dict) and lc.get("workdir"):
        raw = str(lc["workdir"])
    return Path(raw).expanduser()


def _record_started(problem_id: int) -> None:
    """Insert lc_progress started row when missing."""
    from datetime import datetime
    from datetime import timezone

    from idle.config import resolve_paths
    from idle.db import get_db

    now: str = datetime.now(timezone.utc).isoformat()
    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        row = conn.execute(
            "SELECT status FROM lc_progress WHERE problem_id=?;",
            (problem_id,),
        ).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO lc_progress(problem_id, status,"
                " started_at, solved_at) VALUES(?,?,?,NULL);",
                (problem_id, "started", now),
            )
            conn.commit()
    finally:
        conn.close()


def scaffold_problem(
    detail: dict[str, Any],
    lang: str = "python3",
    workdir: str | None = None,
) -> Path:
    """Scaffold solution.py and test.txt, record start."""
    fid: str = _detail_str(detail, "id", "frontendQuestionId")
    slug: str = _detail_str(detail, "slug", "titleSlug")
    title: str = _detail_str(detail, "title")
    diff: str = _detail_str(detail, "difficulty")
    tags: list[str] = _tag_list(detail)
    sample: str = _detail_str(
        detail, "sample_test_case", "sampleTestCase", "example_testcases"
    )
    if not sample:
        sample = _detail_str(detail, "exampleTestcases")
    base: Path = _resolve_workdir(workdir)
    folder: str = f"{fid}-{slug}" if fid and slug else slug or "problem"
    target_dir: Path = base / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    url: str = f"https://leetcode.com/problems/{slug}/"
    header: str = f"# {fid}. {title} | {diff} | {url} | Tags: {','.join(tags)}"
    body: str = _pick_snippet(detail, lang)
    if not body.endswith("\n"):
        body += "\n"
    solution: Path = target_dir / "solution.py"
    solution.write_text(header + "\n\n" + body, encoding="utf-8")
    test_file: Path = target_dir / "test.txt"
    test_file.write_text(sample + ("\n" if sample and not sample.endswith("\n") else ""), encoding="utf-8")
    try:
        _record_started(int(fid))
    except ValueError:
        pass
    return solution
