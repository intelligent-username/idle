"""Adaptive drill text from weak keys and bigrams."""

import random
import sqlite3

WEAK_A = 0.7
WEAK_B = 0.3
TOP_K = 12
LAST_N = 20


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
    """Score chars by miss rate and latency.

    Signature: (conn, last_n) -> {char: score}.
    Test: 5 sessions with z missed score_keys(conn)["z"] > ["e"].
    """
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


def _word_weight(word: str, weak_chars: set[str], weak_bigrams: set[str]) -> float:
    hits: int = sum(1 for ch in word if ch in weak_chars)
    hits += sum(1 for bg in _bigrams_of(word) if bg in weak_bigrams)
    return 1.0 + float(hits)


def generate_drill_text(
    conn: sqlite3.Connection, words: list[str], length: int = 30
) -> str:
    """Build drill text weighted toward weak units.

    Signature: (conn, words, length) -> space joined text.
    Test: with 5 weak-z sessions generate_drill_text(conn, ["zzz","eee"]) has more zzz.
    """
    if not words or length <= 0:
        return ""
    if _session_count(conn) < 5:
        picked: list[str] = random.choices(words, k=length)
        return " ".join(picked)
    char_scores: dict[str, float] = score_keys(conn, LAST_N)
    bigram_scores: dict[str, float] = _bigram_scores(conn, LAST_N)
    if not char_scores and not bigram_scores:
        picked = random.choices(words, k=length)
        return " ".join(picked)
    weak_chars: set[str] = _top_set(char_scores, TOP_K)
    weak_bigrams: set[str] = _top_set(bigram_scores, TOP_K)
    weights: list[float] = [_word_weight(w, weak_chars, weak_bigrams) for w in words]
    chosen: list[str] = random.choices(words, weights=weights, k=length)
    return " ".join(chosen)
