"""LeetCode CLI commands compatibility module."""

from __future__ import annotations

from typing import Any

RELOGIN_MSG = "Session expired. Run: idle lc login"


def _filter_problems(
    problems: list[dict[str, Any]],
    difficulty: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Filter problem list by difficulty, tag, and status."""
    res = list(problems)
    if difficulty:
        res = [p for p in res if str(p.get("difficulty", "")).lower() == difficulty.lower()]
    if tag:
        res = [p for p in res if tag.lower() in [t.lower() for t in p.get("tags", [])]]
    if status:
        res = [p for p in res if str(p.get("status", "")).lower() == status.lower()]
    return res[:limit]


def _status_label(status: Any) -> str:
    """Return status label for problem row."""
    if isinstance(status, dict):
        status = status.get("status")
    if status == "ac":
        return "SOLVED"
    elif status == "notac":
        return "ATTEMPTED"
    elif isinstance(status, str):
        return status.upper()
    return "TODO"


def _find_in_list(problems: list[dict[str, Any]], key: str) -> dict[str, Any] | None:
    """Find problem by id or slug."""
    key_str = str(key).strip().lower()
    for p in problems:
        if str(p.get("id", "")).strip().lower() == key_str or str(p.get("slug", "")).strip().lower() == key_str:
            return p
    return None


def _format_detail(detail: dict[str, Any]) -> str:
    """Format detail view text."""
    from idle.lc.render import html_to_text

    title = detail.get("title", "Untitled")
    slug = detail.get("slug", "")
    raw_content = detail.get("content", "") or detail.get("content_html", "")
    text = html_to_text(raw_content) if raw_content else ""
    return f"=== {title} ({slug}) ===\n\n{text}"


def _verdict_str(res: dict[str, Any]) -> str:
    """Format verdict summary string."""
    status_msg = res.get("status_msg", "Accepted")
    return str(status_msg)


def _record_attempt(
    problem_id_or_slug: Any,
    action: str = "test",
    verdict: str = "",
    detail_or_res: Any = None,
    conn: Any = None,
) -> None:
    """Record attempt in database."""
    pass


def _mark_solved(
    problem_id_or_slug: Any,
    question_id: Any = None,
    conn: Any = None,
) -> None:
    """Mark problem solved in database."""
    pass
