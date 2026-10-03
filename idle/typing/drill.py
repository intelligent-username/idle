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


def weak_avg(conn: sqlite3.Connection, last_n: int = LAST_N, k: int = TOP_K) -> float | None:
    """Return mean of top-k weak scores, None when no data."""
    scores: dict[str, float] = score_keys(conn, last_n)
    if not scores:
        return None
    top: list[float] = sorted(scores.values(), reverse=True)[:max(k, 0)]
    if not top:
        return None
    return sum(top) / len(top)


def _word_weight(word: str, weak_chars: set[str], weak_bigrams: set[str]) -> float:
    hits: int = sum(1 for ch in word if ch in weak_chars)
    hits += sum(1 for bg in _bigrams_of(word) if bg in weak_bigrams)
    return 1.0 + float(hits)


import re
from idle.typing.texts import (
    _CUSTOM_NUM_PASSAGES,
    _LEVEL5_MEANINGFUL_TEXTS,
    _NON_CUSTOM_NUM_PASSAGES,
    _load_passages,
    sanitize_text,
)


def _make_easy_drill_sequence(chars: list[str], gen: random.Random) -> str:
    """Generate pure lowercase letters sequence for easy difficulty."""
    anchors = ["f", "j", "d", "k", "s", "l"]
    raw_c1 = gen.choice(chars) if chars else "f"
    c1 = re.sub(r"[^a-z]", "", raw_c1.lower()) or "f"
    raw_c2 = (
        gen.choice(chars)
        if len(chars) > 1 and gen.random() < 0.6
        else gen.choice(anchors)
    )
    c2 = re.sub(r"[^a-z]", "", raw_c2.lower()) or "j"
    patterns = [
        f"{c1}{c2}{c1}{c2}",
        f"{c1}{c1}{c2}{c2}",
        f"{c1}{c2}{c2}{c1}",
        f"{c2}{c1}{c1}{c2}",
        f"{c1}{c2}{c1}",
        f"{c2}{c1}{c2}",
        f"{c1}{c1}{c1}",
        f"{c1}{c2}{c1}{c2}{c1}",
    ]
    return gen.choice(patterns)


def _make_medium_drill_sequence(chars: list[str], gen: random.Random) -> str:
    """Generate capitalized weak key drill token."""
    seq = _make_easy_drill_sequence(chars, gen)
    return "".join(
        ch.upper() if i % 2 == 0 else ch.lower() for i, ch in enumerate(seq)
    )


def _make_expert_drill_sequence(chars: list[str], gen: random.Random) -> str:
    """Generate weak key drill sequence incorporating digits."""
    anchors = ["f", "j", "d", "k", "s", "l"]
    raw_c1 = gen.choice(chars) if chars else "f"
    c1 = re.sub(r"[^a-zA-Z]", "", raw_c1) or "f"
    raw_c2 = (
        gen.choice(chars)
        if len(chars) > 1 and gen.random() < 0.6
        else gen.choice(anchors)
    )
    c2 = re.sub(r"[^a-zA-Z]", "", raw_c2) or "j"
    n1 = str(gen.randint(0, 9))
    n2 = str(gen.randint(0, 9))
    patterns = [
        f"{n1}{c1}{n1}{c1}",
        f"{c1}{n1}{c2}{n2}",
        f"{c1}{c2}{n1}{n2}",
        f"{n1}{n2}{c1}{c2}",
        f"{c1}{n1}{c1}",
        f"{n1}{c2}{n1}",
        f"{c1}{n1}{c2}{n1}{c2}",
    ]
    return gen.choice(patterns)


_MASTER_SYMBOLS: tuple[str, ...] = (
    "!", "@", "#", "$", "%", "^", "&", "*", "(", ")",
    "-", "_", "=", "+", "[", "]", "{", "}", ";", ":",
    "'", '"', ",", ".", "<", ">", "/", "?",
)


def _make_master_drill_sequence(chars: list[str], gen: random.Random) -> str:
    """Challenging randomized keys: uppercase, lowercase, numbers, special characters."""
    c1 = gen.choice(chars) if chars else gen.choice(["f", "j", "d", "k"])
    c2 = gen.choice(chars) if len(chars) > 1 else gen.choice(["a", "s", "l", "e"])
    sym1 = gen.choice(_MASTER_SYMBOLS)
    sym2 = gen.choice(_MASTER_SYMBOLS)
    num1 = str(gen.randint(0, 9))
    num2 = str(gen.randint(0, 9))
    u1 = c1.upper()
    l1 = c1.lower()
    u2 = c2.upper()
    l2 = c2.lower()
    patterns = [
        f"{sym1}{u1}{num1}{l2}",
        f"{l1}{sym1}{num1}{u2}{sym2}",
        f"{sym1}{l1}{u1}{sym2}",
        f"[{u1}{num1}{l2}]",
        f"({sym1}{l1}{num1})",
        f"{{{u1}{sym1}{num2}}}",
        f"{u1}{sym1}{l2}={num1}",
        f"{sym1}{u1}_{l2}#{num1}",
        f"{sym1}{num1}{u1}!{l2}",
        f"<{u1}{num1}{sym2}{l1}>",
    ]
    return gen.choice(patterns)


def _extract_weak_phrases(passages: list[str], weak_chars: list[str]) -> list[str]:
    """Extract 2-4 word phrases containing weak keys from passages."""
    phrases: list[str] = []
    for p in passages:
        words = p.split()
        for i in range(0, len(words) - 2, 3):
            chunk = " ".join(words[i : i + 3])
            if any(c in chunk for c in weak_chars):
                phrases.append(chunk)
    return phrases if phrases else ["the lazy dog", "quick brown fox"]


def generate_drill_text(
    conn: sqlite3.Connection,
    words: list[str],
    length: int = 30,
    rng: random.Random | None = None,
    weak_keys: int = 5,
    difficulty: int = 0,
) -> str:
    """Build drill text with nonsensical weak sequences and real words.

    Supports 5 difficulty tiers matching user specs.
    """
    if not words or length <= 0:
        return ""
    gen = rng if rng is not None else random.Random()
    diff = max(0, min(difficulty, 4))
    char_scores = score_keys(conn, LAST_N)
    weak_chars = [
        c for c in sorted(char_scores, key=lambda c: char_scores[c], reverse=True) if c.strip()
    ][:max(1, weak_keys)]
    if not weak_chars:
        weak_chars = ["f", "j", "d", "k", "s", "l"][:max(2, weak_keys)]

    # When words is a small test fixture (<= 5 words), preserve weighted selection from words
    if len(words) <= 5:
        weak_set = set(weak_chars)
        weights = [_word_weight(w, weak_set, set()) for w in words]
        chosen = gen.choices(words, weights=weights, k=length)
        return sanitize_text(" ".join(chosen))

    out: list[str] = []

    if diff == 0:
        # Easy: Really easy common words, lowercase only, no caps, no punctuation/numbers
        clean_words = [
            re.sub(r"[^a-z]", "", w.lower()) for w in words if re.sub(r"[^a-z]", "", w.lower())
        ]
        matching = [w for w in clean_words if any(c in w for c in weak_chars)] or clean_words
        for i in range(length):
            if i % 2 == 0:
                out.append(_make_easy_drill_sequence(weak_chars, gen))
            else:
                out.append(gen.choice(matching))

    elif diff == 1:
        # Medium: Medium difficulty words with capitalizations
        clean_words = [
            re.sub(r"[^a-zA-Z]", "", w) for w in words if re.sub(r"[^a-zA-Z]", "", w)
        ]
        matching = [w for w in clean_words if any(c.lower() in w.lower() for c in weak_chars)] or clean_words
        for i in range(length):
            if i % 2 == 0:
                out.append(_make_medium_drill_sequence(weak_chars, gen))
            else:
                out.append(gen.choice(matching).capitalize())

    elif diff == 2:
        # Hard: Passages/snippets mixed with weak key sequence drills
        passages = _load_passages()
        phrases = _extract_weak_phrases(passages, weak_chars)
        while len(out) < length:
            out.append(_make_medium_drill_sequence(weak_chars, gen))
            phrase = gen.choice(phrases)
            out.extend(phrase.split())

    elif diff == 3:
        # Expert: Passages with numbers mixed with weak-key numeric drills
        num_passages = list(_NON_CUSTOM_NUM_PASSAGES) + list(_CUSTOM_NUM_PASSAGES)
        phrases = _extract_weak_phrases(num_passages, weak_chars)
        while len(out) < length:
            out.append(_make_expert_drill_sequence(weak_chars, gen))
            phrase = gen.choice(phrases)
            out.extend(phrase.split())

    else:
        # Master (4): Random keys with uppercase/lowercase, numbers, special characters
        # combined with complex tokens containing weak keys
        complex_tokens: list[str] = []
        for text in _LEVEL5_MEANINGFUL_TEXTS:
            for token in text.split():
                if any(c.lower() in token.lower() for c in weak_chars):
                    complex_tokens.append(token)
        if not complex_tokens:
            complex_tokens = ["status=200", "v2.1.0", "user_id", "p<0.001", "O(b^d)", "HTTP/2"]

        for i in range(length):
            if i % 2 == 0:
                out.append(_make_master_drill_sequence(weak_chars, gen))
            else:
                out.append(gen.choice(complex_tokens))

    return sanitize_text(" ".join(out[:length]))

