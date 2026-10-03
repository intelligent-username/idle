"""Engine math tests, no terminal or network."""

from idle.typing.engine import Keystroke
from idle.typing.engine import calc_accuracy
from idle.typing.engine import calc_consistency
from idle.typing.engine import calc_net_wpm
from idle.typing.engine import calc_raw_wpm
from idle.typing.engine import update_stats


def test_raw_wpm_basic() -> None:
    assert calc_raw_wpm(300, 60.0) == 60.0


def test_raw_wpm_zero_elapsed() -> None:
    value: float = calc_raw_wpm(25, 0.0)
    assert value > 0.0


def test_raw_wpm_zero_chars() -> None:
    assert calc_raw_wpm(0, 60.0) == 0.0


def test_net_wpm_basic() -> None:
    assert calc_net_wpm(60.0, 6, 60.0) == 54.0


def test_net_wpm_floor_zero() -> None:
    assert calc_net_wpm(10.0, 100, 60.0) == 0.0


def test_net_wpm_zero_elapsed() -> None:
    assert calc_net_wpm(50.0, 1, 0.0) == 0.0


def test_accuracy_basic() -> None:
    assert calc_accuracy(9, 10) == 0.9


def test_accuracy_zero_total() -> None:
    assert calc_accuracy(0, 0) == 0.0


def test_consistency_empty() -> None:
    assert calc_consistency([]) == 1.0


def test_consistency_single() -> None:
    assert calc_consistency([55.0]) == 1.0


def test_consistency_uniform() -> None:
    assert calc_consistency([50.0, 50.0, 50.0]) == 1.0


def test_consistency_mean_zero() -> None:
    assert calc_consistency([0.0, 0.0]) == 1.0


def test_consistency_varied() -> None:
    value: float = calc_consistency([40.0, 60.0, 40.0, 60.0])
    assert 0.0 < value < 1.0


def test_consistency_floored_at_zero() -> None:
    value: float = calc_consistency([1000.0, 10.0, 10.0])
    assert value == 0.0


def test_update_stats_counts() -> None:
    per_key: dict[str, dict[str, float]] = {}
    per_bigram: dict[str, dict[str, float]] = {}
    update_stats(Keystroke("a", "a", 50.0, True), per_key, per_bigram, None)
    update_stats(Keystroke("x", "a", 70.0, False), per_key, per_bigram, "h")
    assert per_key["a"]["attempts"] == 2.0
    assert per_key["a"]["misses"] == 1.0
    assert per_key["a"]["total_latency_ms"] == 120.0
    assert per_bigram["ha"]["count"] == 1.0
    assert per_bigram["ha"]["total_latency_ms"] == 70.0


def test_update_stats_no_bigram_without_prev() -> None:
    per_key: dict[str, dict[str, float]] = {}
    per_bigram: dict[str, dict[str, float]] = {}
    update_stats(Keystroke("b", "b", 20.0, True), per_key, per_bigram)
    assert per_bigram == {}
