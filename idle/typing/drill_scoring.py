"""Adaptive drill key & bigram scoring algorithms based on history."""

import sqlite3

__all__: list[str] = [
    "LAST_N",
    "TOP_K",
    "WEAK_A",
    "WEAK_B",
    "score_keys",
    "weak_avg",
    "word_weight",
]

WEAK_A: float = 0.7
WEAK_B: float = 0.3
TOP_K: int = 12
LAST_N: int = 20


def _recent_ids(conn: sqlite3.Connection, last_n: int) -> list[int]:
    rows = conn.execute(
        "SELECT id FROM typing_sessions ORDER BY id DESC LIMIT ?;",
        (last_n,),
    ).fetchall()
    return [int(r[0]) for r in rows]


def _ids_and_weights(
    conn: sqlite3.Connection, last_n: int
) -> tuple[list[int], dict[int, float]]:
    ids: list[int] = _recent_ids(conn, last_n)
    weights: dict[int, float] = {s: 1.0 / (1.0 + i) for i, s in enumerate(ids)}
    return ids, weights


def _session_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM typing_sessions;").fetchone()
    return int(row[0]) if row else 0


def score_keys(conn: sqlite3.Connection, last_n: int = LAST_N) -> dict[str, float]:
    """Score chars by miss rate and latency."""
    ids, weights = _ids_and_weights(conn, last_n)
    if not ids:
        return {}
    marks: str = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT session_id, char, attempts, misses, total_latency_ms "
        f"FROM key_stats WHERE session_id IN ({marks});",
        ids,
    ).fetchall()
    att: dict[str, float] = {}
    miss: dict[str, float] = {}
    lat: dict[str, float] = {}
    for sid, ch, a, m, t in rows:
        w: float = weights.get(int(sid), 0.0)
        c: str = str(ch)
        att[c] = att.get(c, 0.0) + float(a) * w
        miss[c] = miss.get(c, 0.0) + float(m) * w
        lat[c] = lat.get(c, 0.0) + float(t) * w
    avg: dict[str, float] = {c: lat[c] / att[c] for c in att if att[c] > 0}
    if not avg:
        return {}
    lo: float = min(avg.values())
    hi: float = max(avg.values())
    span: float = (hi - lo) if (hi - lo) != 0 else 1.0
    out: dict[str, float] = {}
    for c in avg:
        miss_rate: float = miss.get(c, 0.0) / att[c] if att[c] > 0 else 0.0
        norm_lat: float = (avg[c] - lo) / span
        out[c] = miss_rate * WEAK_A + norm_lat * WEAK_B
    return out


def _bigram_scores(conn: sqlite3.Connection, last_n: int = LAST_N) -> dict[str, float]:
    ids, weights = _ids_and_weights(conn, last_n)
    if not ids:
        return {}
    marks: str = ",".join("?" for _ in ids)
    rows = conn.execute(
        f"SELECT session_id, bigram, count, total_latency_ms "
        f"FROM bigram_stats WHERE session_id IN ({marks});",
        ids,
    ).fetchall()
    cnt: dict[str, float] = {}
    lat: dict[str, float] = {}
    for sid, bg, c, t in rows:
        w: float = weights.get(int(sid), 0.0)
        b: str = str(bg)
        cnt[b] = cnt.get(b, 0.0) + float(c) * w
        lat[b] = lat.get(b, 0.0) + float(t) * w
    avg: dict[str, float] = {b: lat[b] / cnt[b] for b in cnt if cnt[b] > 0}
    if not avg:
        return {}
    lo: float = min(avg.values())
    hi: float = max(avg.values())
    span: float = (hi - lo) if (hi - lo) != 0 else 1.0
    return {b: (avg[b] - lo) / span for b in avg}


def _bigrams_of(word: str) -> list[str]:
    return [word[i : i + 2] for i in range(len(word) - 1)]


def _top_set(scores: dict[str, float], k: int = TOP_K) -> set[str]:
    ranked: list[str] = sorted(scores, key=lambda c: scores[c], reverse=True)
    return set(ranked[:k])


def weak_avg(conn: sqlite3.Connection, last_n: int = LAST_N, k: int = TOP_K) -> float | None:
    """Return mean of top-k weak scores, None when no data."""
    scores: dict[str, float] = score_keys(conn, last_n)
    if not scores:
        return None
    top: list[float] = sorted(scores.values(), reverse=True)[: max(k, 0)]
    if not top:
        return None
    return sum(top) / len(top)


def word_weight(
    word: str,
    char_scores: dict[str, float] | set[str],
    weak_bigrams: set[str] | None = None,
) -> float:
    """Calculate weighting for a word given weak keys scores or set."""
    if isinstance(char_scores, dict):
        hits: float = sum(float(char_scores.get(ch, 0.0)) * 10.0 for ch in word)
        return 1.0 + hits
    hit_count: int = sum(1 for ch in word if ch in char_scores)
    if weak_bigrams:
        hit_count += sum(1 for bg in _bigrams_of(word) if bg in weak_bigrams)
    return 1.0 + float(hit_count)
