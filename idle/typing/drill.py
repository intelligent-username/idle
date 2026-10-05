"""Adaptive drill text from weak keys and bigrams."""

import random
import re
import sqlite3

from idle.typing.drill_scoring import (
    LAST_N,
    TOP_K,
    WEAK_A,
    WEAK_B,
    score_keys,
    weak_avg,
    word_weight,
)
from idle.typing.texts import (
    _CUSTOM_NUM_PASSAGES,
    _LEVEL5_MEANINGFUL_TEXTS,
    _NON_CUSTOM_NUM_PASSAGES,
    _load_passages,
    sanitize_text,
)

__all__: list[str] = [
    "LAST_N",
    "TOP_K",
    "WEAK_A",
    "WEAK_B",
    "generate_drill_text",
    "score_keys",
    "weak_avg",
]

_MASTER_SYMBOLS: tuple[str, ...] = (
    "!", "@", "#", "$", "%", "^", "&", "*", "(", ")",
    "-", "_", "=", "+", "[", "]", "{", "}", ";", ":",
    "'", '"', ",", ".", "<", ">", "/", "?",
)


def _make_easy_drill_sequence(chars: list[str], gen: random.Random) -> str:
    """Generate pure lowercase letters sequence for easy difficulty."""
    anchors = ["f", "j", "d", "k", "s", "l"]
    raw_c1 = gen.choice(chars) if chars else "f"
    c1 = re.sub(r"[^a-z]", "", raw_c1.lower()) or "f"
    raw_c2 = gen.choice(chars) if len(chars) > 1 and gen.random() < 0.6 else gen.choice(anchors)
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
    return "".join(ch.upper() if i % 2 == 0 else ch.lower() for i, ch in enumerate(seq))


def _make_expert_drill_sequence(chars: list[str], gen: random.Random) -> str:
    """Generate weak key drill sequence incorporating digits."""
    anchors = ["f", "j", "d", "k", "s", "l"]
    raw_c1 = gen.choice(chars) if chars else "f"
    c1 = re.sub(r"[^a-zA-Z]", "", raw_c1) or "f"
    raw_c2 = gen.choice(chars) if len(chars) > 1 and gen.random() < 0.6 else gen.choice(anchors)
    c2 = re.sub(r"[^a-zA-Z]", "", raw_c2) or "j"
    n1, n2 = str(gen.randint(0, 9)), str(gen.randint(0, 9))
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


def _make_master_drill_sequence(chars: list[str], gen: random.Random) -> str:
    """Challenging randomized keys: uppercase, lowercase, numbers, special characters."""
    c1 = gen.choice(chars) if chars else gen.choice(["f", "j", "d", "k"])
    c2 = gen.choice(chars) if len(chars) > 1 else gen.choice(["a", "s", "l", "e"])
    sym1, sym2 = gen.choice(_MASTER_SYMBOLS), gen.choice(_MASTER_SYMBOLS)
    num1, num2 = str(gen.randint(0, 9)), str(gen.randint(0, 9))
    u1, l1 = c1.upper(), c1.lower()
    u2, l2 = c2.upper(), c2.lower()
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
    """Build drill text with nonsensical weak sequences and real words."""
    if not words or length <= 0:
        return ""
    gen = rng if rng is not None else random.Random()
    diff = max(0, min(difficulty, 4))
    char_scores = score_keys(conn, LAST_N)
    weak_chars = [
        c for c in sorted(char_scores, key=lambda c: char_scores[c], reverse=True) if c.strip()
    ][: max(1, weak_keys)]
    if not weak_chars:
        weak_chars = ["f", "j", "d", "k", "s", "l"][: max(2, weak_keys)]

    if len(words) <= 5:
        weights = [word_weight(w, char_scores if char_scores else set(weak_chars)) for w in words]
        return sanitize_text(" ".join(gen.choices(words, weights=weights, k=length)))

    out: list[str] = []
    if diff == 0:
        clean = [re.sub(r"[^a-z]", "", w.lower()) for w in words if re.sub(r"[^a-z]", "", w.lower())]
        matching = [w for w in clean if any(c in w for c in weak_chars)] or clean
        for i in range(length):
            out.append(_make_easy_drill_sequence(weak_chars, gen) if i % 2 == 0 else gen.choice(matching))
    elif diff == 1:
        clean = [re.sub(r"[^a-zA-Z]", "", w) for w in words if re.sub(r"[^a-zA-Z]", "", w)]
        matching = [w for w in clean if any(c.lower() in w.lower() for c in weak_chars)] or clean
        for i in range(length):
            out.append(_make_medium_drill_sequence(weak_chars, gen) if i % 2 == 0 else gen.choice(matching).capitalize())
    elif diff == 2:
        phrases = _extract_weak_phrases(_load_passages(), weak_chars)
        while len(out) < length:
            out.append(_make_medium_drill_sequence(weak_chars, gen))
            out.extend(gen.choice(phrases).split())
    elif diff == 3:
        phrases = _extract_weak_phrases(list(_NON_CUSTOM_NUM_PASSAGES) + list(_CUSTOM_NUM_PASSAGES), weak_chars)
        while len(out) < length:
            out.append(_make_expert_drill_sequence(weak_chars, gen))
            out.extend(gen.choice(phrases).split())
    else:
        tokens = [tok for t in _LEVEL5_MEANINGFUL_TEXTS for tok in t.split() if any(c.lower() in tok.lower() for c in weak_chars)]
        if not tokens:
            tokens = ["status=200", "v2.1.0", "user_id", "p<0.001", "O(b^d)", "HTTP/2"]
        for i in range(length):
            out.append(_make_master_drill_sequence(weak_chars, gen) if i % 2 == 0 else gen.choice(tokens))

    return sanitize_text(" ".join(out[:length]))
