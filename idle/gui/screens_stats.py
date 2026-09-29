"""Stats and config screens with pure getters."""

from pathlib import Path
from typing import Any

__all__: list[str] = [
    "get_recent_sessions",
    "get_best_avg",
    "get_solved_by_difficulty",
    "get_recent_attempts",
    "get_streak",
    "load_stats",
    "load_config_view",
    "format_config_lines",
    "handle_stats",
    "handle_config",
    "draw_stats",
    "draw_config",
]

EMPTY_TYPING_MSG: str = "no sessions yet. Run: type"
EMPTY_LC_MSG: str = "no leetcode activity yet"


def get_recent_sessions(conn: Any, limit: int = 20) -> list[Any]:
    """Fetch last N typing sessions newest first."""
    cur: Any = conn.execute(
        "SELECT id, ts, mode, duration_s, net_wpm, accuracy"
        " FROM typing_sessions ORDER BY id DESC LIMIT ?;",
        (max(limit, 0),),
    )
    return list(cur.fetchall())


def get_best_avg(conn: Any) -> tuple[float | None, float | None]:
    """Return Best and 7-day average WPM."""
    from idle.db import get_7day_avg
    from idle.db import get_best

    return (get_best(conn), get_7day_avg(conn))


def get_solved_by_difficulty(conn: Any) -> dict[str, int]:
    """Return solved counts grouped by difficulty."""
    rows: Any = conn.execute(
        "SELECT p.difficulty, COUNT(*) FROM lc_problems p"
        " JOIN lc_progress g ON p.id=g.problem_id"
        " WHERE g.status='solved' GROUP BY p.difficulty;"
    ).fetchall()
    out: dict[str, int] = {}
    for diff, count in rows:
        out[str(diff)] = int(count)
    return out


def get_recent_attempts(conn: Any, limit: int = 10) -> list[Any]:
    """Fetch recent LC attempts newest first."""
    cur: Any = conn.execute(
        "SELECT problem_id, ts, kind, verdict FROM lc_attempts"
        " ORDER BY id DESC LIMIT ?;",
        (max(limit, 0),),
    )
    return list(cur.fetchall())


def get_streak(conn: Any) -> tuple[int, int]:
    """Return solve streak and active day count."""
    from idle.lc.commands import _calc_streak

    rows: Any = conn.execute(
        "SELECT substr(solved_at,1,10) FROM lc_progress"
        " WHERE solved_at IS NOT NULL;"
    ).fetchall()
    days: list[str] = [str(r[0]) for r in rows if r[0]]
    return (_calc_streak(days), len(set(days)))


def load_stats(db_path: str | Path, limit: int = 20) -> dict[str, Any]:
    """Load all stats sections, empty friendly on error."""
    from idle.db import get_db

    empty: dict[str, Any] = {
        "recent": [],
        "best": None,
        "avg": None,
        "by_diff": {},
        "attempts": [],
        "streak": 0,
        "active": 0,
    }
    try:
        conn = get_db(Path(db_path))
    except OSError:
        return empty
    try:
        empty["recent"] = get_recent_sessions(conn, limit)
        best, avg = get_best_avg(conn)
        empty["best"] = best
        empty["avg"] = avg
        empty["by_diff"] = get_solved_by_difficulty(conn)
        empty["attempts"] = get_recent_attempts(conn)
        streak, active = get_streak(conn)
        empty["streak"] = streak
        empty["active"] = active
        return empty
    finally:
        conn.close()


def load_config_view() -> dict[str, Any]:
    """Load paths and config read-only, defaults on error."""
    from idle.config import DEFAULT_CONFIG
    from idle.config import load_config
    from idle.config import resolve_paths

    try:
        db_path, cfg_path, auth_path = resolve_paths()
    except OSError:
        return {"config": DEFAULT_CONFIG, "error": True}
    try:
        cfg: dict[str, Any] = load_config()
    except OSError:
        cfg = {k: dict(v) for k, v in DEFAULT_CONFIG.items()}
    return {
        "db_path": db_path,
        "config_path": cfg_path,
        "auth_path": auth_path,
        "config": cfg,
    }


def format_config_lines(view: dict[str, Any]) -> list[str]:
    """Format read-only config view as text lines."""
    lines: list[str] = []
    if "db_path" in view:
        lines.append(f"db: {view['db_path']}")
    if "config_path" in view:
        lines.append(f"config: {view['config_path']}")
    cfg: Any = view.get("config", {})
    typing: Any = cfg.get("typing", {}) if isinstance(cfg, dict) else {}
    lc: Any = cfg.get("lc", {}) if isinstance(cfg, dict) else {}
    if isinstance(typing, dict):
        for key in ("default_mode", "default_time", "word_list", "stop_on_error"):
            lines.append(f"typing.{key} = {typing.get(key, '')}")
    if isinstance(lc, dict):
        for key in ("language", "workdir"):
            lines.append(f"lc.{key} = {lc.get(key, '')}")
    lines.append("read-only (edit config.toml manually)")
    return lines


def _is_back(event: Any) -> bool:
    """Return True when Esc pressed."""
    import pygame

    return int(getattr(event, "type", -1)) == pygame.KEYDOWN and int(
        getattr(event, "key", 0)
    ) == pygame.K_ESCAPE


def handle_stats(event: Any) -> bool:
    """Return True when stats screen should go back."""
    return _is_back(event)


def handle_config(event: Any) -> bool:
    """Return True when config screen should go back."""
    return _is_back(event)


def _stat_lines(data: dict[str, Any]) -> list[str]:
    """Build stats text lines with empty friendly fallback."""
    lines: list[str] = ["stats (Esc back)", ""]
    best: Any = data.get("best")
    avg: Any = data.get("avg")
    lines.append(f"Best: {best:.1f} WPM" if best is not None else "Best: --")
    lines.append(f"7-day: {avg:.1f} WPM" if avg is not None else "7-day: --")
    lines.append("")
    recent: Any = data.get("recent", [])
    if not recent:
        lines.append(EMPTY_TYPING_MSG)
    else:
        lines.append(f"{'id':>5}  {'mode':<6}  {'net':>6}  {'acc':>6}")
        for row in recent[:10]:
            lines.append(_format_session(row))
    lines.append("")
    lines.extend(_lc_lines(data))
    return lines


def _format_session(row: Any) -> str:
    """Format one typing session row."""
    sid, _ts, mode, _secs, net, acc = row[0], row[1], row[2], row[3], row[4], row[5]
    return f"{int(sid):>5}  {str(mode):<6}  {float(net):>6.1f}  {float(acc) * 100.0:>5.1f}%"


def _lc_lines(data: dict[str, Any]) -> list[str]:
    """Build LC difficulty, recent, and streak lines."""
    lines: list[str] = []
    by_diff: Any = data.get("by_diff", {})
    if not by_diff:
        lines.append("solved: 0")
    else:
        for diff in sorted(by_diff):
            lines.append(f"solved {diff}: {by_diff[diff]}")
    attempts: Any = data.get("attempts", [])
    if not attempts:
        lines.append(EMPTY_LC_MSG)
    else:
        for pid, ts, kind, verdict in attempts[:5]:
            lines.append(f"{pid} {str(ts)[:19]} {kind} {verdict}")
    lines.append(f"streak: {data.get('streak', 0)} days ({data.get('active', 0)} active)")
    return lines


def _draw_lines(surface: Any, lines: list[str]) -> None:
    """Draw text lines vertically with theme font."""
    from idle.gui import theme

    font: Any = theme.get_font(18)
    surface.fill(theme.BG)
    y: int = 20
    for line in lines:
        img: Any = font.render(line, True, theme.FG)
        surface.blit(img, (20, y))
        y += font.get_linesize() + 2


def draw_stats(surface: Any, state: Any, data: dict[str, Any] | None = None) -> None:
    """Draw stats screen, loading from state when needed."""
    if data is None:
        db_path: str = str(getattr(state, "db_path", "") or "")
        limit: int = int(getattr(state, "limit", 20) or 20)
        data = load_stats(db_path, limit) if db_path else load_stats(".", limit)
    _draw_lines(surface, _stat_lines(data))


def draw_config(surface: Any, state: Any, view: dict[str, Any] | None = None) -> None:
    """Draw read-only config screen."""
    if view is None:
        view = load_config_view()
    lines: list[str] = ["config (Esc back, read-only)", ""]
    lines.extend(format_config_lines(view))
    _draw_lines(surface, lines)
