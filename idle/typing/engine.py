"""Pure typing metrics with no terminal IO."""

import statistics
from dataclasses import dataclass


@dataclass
class Keystroke:
    """Single key press against expected text."""

    char: str
    expected: str
    latency_ms: float
    correct: bool


def calc_raw_wpm(typed_chars: int, elapsed_s: float) -> float:
    """Return gross words per minute."""
    minutes: float = max(elapsed_s / 60.0, 1e-9)
    return (typed_chars / 5.0) / minutes


def calc_net_wpm(raw_wpm: float, uncorrected_errors: int, elapsed_s: float) -> float:
    """Return net WPM floored at zero."""
    minutes: float = max(elapsed_s / 60.0, 1e-9)
    penalty: float = uncorrected_errors / minutes
    return max(0.0, raw_wpm - penalty)


def calc_accuracy(correct: int, total: int) -> float:
    """Return correct over total, zero when empty."""
    if total <= 0:
        return 0.0
    return correct / total


def calc_consistency(wpm_per_sec: list[float]) -> float:
    """Return 1 minus variation of per-second WPM."""
    if len(wpm_per_sec) < 2:
        return 1.0
    mean: float = statistics.fmean(wpm_per_sec)
    if mean == 0:
        return 1.0
    spread: float = statistics.stdev(wpm_per_sec)
    return 1.0 - (spread / mean)


def update_stats(
    keystroke: Keystroke,
    per_key: dict[str, dict[str, float]],
    per_bigram: dict[str, dict[str, float]],
    prev_char: str | None = None,
) -> None:
    """Fold one keystroke into mutable aggregates.

    Test: Keystroke('a','a',50.0,True) adds one
    attempt to per_key['a'] and one count to
    per_bigram['xa'] when prev_char is 'x'.
    """
    entry: dict[str, float] = per_key.setdefault(
        keystroke.expected,
        {"attempts": 0.0, "misses": 0.0, "total_latency_ms": 0.0},
    )
    entry["attempts"] += 1.0
    if not keystroke.correct:
        entry["misses"] += 1.0
    entry["total_latency_ms"] += keystroke.latency_ms
    if prev_char is None:
        return
    bigram: str = prev_char + keystroke.expected
    bentry: dict[str, float] = per_bigram.setdefault(
        bigram, {"count": 0.0, "total_latency_ms": 0.0}
    )
    bentry["count"] += 1.0
    bentry["total_latency_ms"] += keystroke.latency_ms
