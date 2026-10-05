"""Formatting and summary presentation for typing test results."""

from typing import Any

__all__: list[str] = [
    "SPARK_BLOCKS",
    "format_results",
    "show_results",
]

SPARK_BLOCKS: str = "._-~*^#"


def _disp(ch: str) -> str:
    """Show space key visibly."""
    return "space" if ch == " " else ch


def _sparkline(values: list[float]) -> str:
    """Map values to block chars normalized by min-max."""
    if not values:
        return ""
    lo: float = min(values)
    hi: float = max(values)
    if hi <= lo:
        return SPARK_BLOCKS[0] * len(values)
    out: list[str] = []
    last: int = len(SPARK_BLOCKS) - 1
    for v in values:
        ratio: float = (v - lo) / (hi - lo)
        out.append(SPARK_BLOCKS[int(round(ratio * last))])
    return "".join(out)


def _avg_lat(entry: dict[str, float]) -> float:
    """Return average latency for one per-key entry."""
    attempts: float = float(entry.get("attempts", 0.0))
    if attempts <= 0:
        return 0.0
    return float(entry.get("total_latency_ms", 0.0)) / attempts


def _miss_rate(entry: dict[str, float]) -> float:
    """Return misses over attempts for one entry."""
    attempts: float = float(entry.get("attempts", 0.0))
    if attempts <= 0:
        return 0.0
    return float(entry.get("misses", 0.0)) / attempts


def _slowest(per_key: dict[str, dict[str, float]], n: int = 5) -> list[tuple[str, float]]:
    """Return top-n chars by average latency."""
    with_attempts = {k: v for k, v in per_key.items() if float(v.get("attempts", 0.0)) > 0}
    ranked = sorted(with_attempts.items(), key=lambda kv: _avg_lat(kv[1]), reverse=True)
    return [(k, _avg_lat(v)) for k, v in ranked[:n]]


def _most_missed(per_key: dict[str, dict[str, float]], n: int = 5) -> list[tuple[str, float]]:
    """Return top-n chars by miss rate for keys that had misses."""
    with_misses = {k: v for k, v in per_key.items() if float(v.get("misses", 0.0)) > 0}
    ranked = sorted(with_misses.items(), key=lambda kv: _miss_rate(kv[1]), reverse=True)
    return [(k, _miss_rate(v)) for k, v in ranked[:n]]


def _slowest_line(per_key: dict[str, dict[str, float]]) -> str:
    """Return slowest-keys summary line."""
    rows: list[tuple[str, float]] = _slowest(per_key, 5)
    if not rows:
        return "Slowest: --"
    parts: list[str] = [f"{_disp(k)} {v:.0f}ms" for k, v in rows]
    return "Slowest: " + ", ".join(parts)


def _missed_line(per_key: dict[str, dict[str, float]]) -> str:
    """Return most-missed-keys summary line."""
    rows: list[tuple[str, float]] = _most_missed(per_key, 5)
    if not rows:
        return "Most missed: --"
    parts: list[str] = [f"{_disp(k)} {v * 100.0:.0f}%" for k, v in rows]
    return "Most missed: " + ", ".join(parts)


def _resolve_best(result: dict[str, Any], best: float | None) -> float | None:
    """Return explicit best or fallback from result."""
    if best is None and isinstance(result.get("best"), (int, float)):
        return float(result["best"])
    return best


def _resolve_avg(result: dict[str, Any], seven_day_avg: float | None) -> float | None:
    """Return explicit average or fallback from result keys."""
    if seven_day_avg is not None:
        return seven_day_avg
    for key in ("seven_day_avg", "avg7", "avg_7day"):
        val: Any = result.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def _core_lines(result: dict[str, Any]) -> list[str]:
    """Return Net Raw Acc Consistency spark slowest missed lines."""
    net: float = float(result.get("net_wpm", 0.0))
    raw: float = float(result.get("raw_wpm", 0.0))
    acc: float = float(result.get("accuracy", 0.0))
    cons: float = float(result.get("consistency", 0.0))
    spark_vals: list[float] = [float(v) for v in result.get("spark", [])]
    per_key: dict[str, dict[str, float]] = result.get("per_key", {})
    return [
        f"Net WPM: {net:.1f}",
        f"Raw WPM: {raw:.1f}",
        f"Accuracy: {acc * 100.0:.1f}%",
        f"Consistency: {cons * 100.0:.1f}%",
        f"Sparkline: {_sparkline(spark_vals)}",
        _slowest_line(per_key),
        _missed_line(per_key),
    ]


def format_results(
    result: dict[str, Any],
    best: float | None = None,
    seven_day_avg: float | None = None,
) -> list[str]:
    """Return Net Raw Acc Consistency spark slowest missed Best 7-day lines."""
    lines: list[str] = _core_lines(result)
    res_best: float | None = _resolve_best(result, best)
    res_avg: float | None = _resolve_avg(result, seven_day_avg)
    lines.append(f"Best: {res_best:.1f} WPM" if res_best is not None else "Best: --")
    lines.append(f"7-Day Avg: {res_avg:.1f} WPM" if res_avg is not None else "7-Day Avg: --")
    return lines


def show_results(
    result: dict[str, Any],
    best: float | None = None,
    seven_day_avg: float | None = None,
) -> None:
    """Print Net Raw Acc Consistency sparkline slowest missed Best 7-day."""
    print("\n".join(format_results(result, best, seven_day_avg)))
