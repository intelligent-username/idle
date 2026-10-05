"""Text generator and passage builders for typing tests."""

import random
import re

from idle.typing.texts_data import (
    _CUSTOM_NUM_PASSAGES,
    _LEVEL5_MEANINGFUL_TEXTS,
    _NON_CUSTOM_NUM_PASSAGES,
    _SNIPPET_SEP,
    _load_code_chunks,
    _load_passages,
    _load_quotes,
    _read_data_file,
    load_tiered_passages,
    load_words,
    rate_passage,
    sanitize_text,
)

__all__: list[str] = [
    "PUNCT_MARKS",
    "_CUSTOM_NUM_PASSAGES",
    "_LEVEL5_MEANINGFUL_TEXTS",
    "_NON_CUSTOM_NUM_PASSAGES",
    "_SNIPPET_SEP",
    "_load_code_chunks",
    "_load_passages",
    "_load_quotes",
    "_read_data_file",
    "build_difficulty_typing_text",
    "load_tiered_passages",
    "load_words",
    "make_text",
    "rate_passage",
    "sanitize_text",
]

PUNCT_MARKS: tuple[str, ...] = (".", ",", ";", ":", "!", "?")


def _decorate_words(
    picked: list[str], punct: bool, numbers: bool, gen: random.Random
) -> list[str]:
    """Apply numbers and punct sprinkles."""
    out: list[str] = []
    for word in picked:
        token: str = word
        if numbers and gen.random() < 0.10:
            token = str(gen.randint(0, 9999))
        if punct and gen.random() < 0.10:
            token += gen.choice(PUNCT_MARKS)
        out.append(token)
    return out


def _build_sentences_text(num_words: int, numbers: bool, gen: random.Random) -> str:
    """Combine realistic sentences until target word count is satisfied."""
    quotes = _load_quotes() or ["The quick brown fox jumps over the lazy dog."]
    shuffled = list(quotes)
    gen.shuffle(shuffled)
    selected: list[str] = []
    word_count, idx = 0, 0
    while word_count < num_words and idx < len(shuffled) * 4:
        sent = shuffled[idx % len(shuffled)]
        selected.append(sent)
        word_count += len(sent.split())
        idx += 1
    text = " ".join(selected)
    if numbers:
        tokens = text.split()
        for i in range(len(tokens)):
            if gen.random() < 0.08:
                tokens[i] = str(gen.randint(10, 999))
        text = " ".join(tokens)
    return sanitize_text(text)


def _get_passage_snippet(passages: list[str], num_words: int, gen: random.Random) -> str:
    """Extract a passage snippet of appropriate length."""
    p = gen.choice(passages or ["The quick brown fox jumps over the lazy dog."])
    words = p.split()
    if len(words) <= num_words + 10:
        return p
    sentences = re.split(r"(?<=[.!?])\s+", p)
    if len(sentences) <= 1:
        return " ".join(words[:num_words])
    start = gen.randint(0, max(0, len(sentences) - 2))
    accum: list[str] = []
    curr_len = 0
    for s in sentences[start:]:
        accum.append(s)
        curr_len += len(s.split())
        if curr_len >= num_words:
            break
    return sanitize_text(" ".join(accum))


def build_difficulty_typing_text(
    difficulty: int,
    num_words: int = 50,
    rng: random.Random | None = None,
) -> str:
    """Build typing test text according to 5 difficulty tiers."""
    gen: random.Random = rng if rng is not None else random.Random()
    diff = max(0, min(difficulty, 4))
    if diff == 0:
        w200 = load_words(200)
        clean = [re.sub(r"[^a-z]", "", w.lower()) for w in w200 if re.sub(r"[^a-z]", "", w.lower())]
        return sanitize_text(" ".join(gen.choice(clean) for _ in range(num_words)))
    if diff == 1:
        w1000 = load_words(1000)
        clean = [re.sub(r"[^a-zA-Z]", "", w) for w in w1000 if re.sub(r"[^a-zA-Z]", "", w)]
        return sanitize_text(" ".join(gen.choice(clean).capitalize() for _ in range(num_words)))
    if diff == 2:
        t1, t2 = load_tiered_passages()
        pool = t2 if t2 else (t1 or _load_passages())
        return _get_passage_snippet(pool, max(20, min(num_words, 80)), gen)
    if diff == 3:
        candidates = list(_NON_CUSTOM_NUM_PASSAGES) + list(_CUSTOM_NUM_PASSAGES)
        p = gen.choice(candidates)
        if len(p.split()) > num_words + 15:
            sentences = re.split(r"(?<=[.!?])\s+", p)
            accum, curr_len = [], 0
            for s in sentences:
                accum.append(s)
                curr_len += len(s.split())
                if curr_len >= num_words:
                    break
            return sanitize_text(" ".join(accum))
        return sanitize_text(p)
    shuffled = list(_LEVEL5_MEANINGFUL_TEXTS)
    gen.shuffle(shuffled)
    chosen, total, idx = [], 0, 0
    while total < num_words and idx < len(shuffled) * 2:
        sent = shuffled[idx % len(shuffled)]
        chosen.append(sent)
        total += len(sent.split())
        idx += 1
    return sanitize_text(" ".join(chosen))


def make_text(
    mode: str,
    words: list[str] | None = None,
    word_list: int = 200,
    num_words: int = 50,
    punct: bool = False,
    numbers: bool = False,
    language: str = "python",
    rng: random.Random | None = None,
) -> str:
    """Build test text for mode."""
    gen: random.Random = rng if rng is not None else random.Random()
    if mode in ("time", "words", "sentence", "sentences"):
        if words is not None:
            if not words:
                raise ValueError("empty word source")
            picked = [gen.choice(words) for _ in range(num_words)]
            return sanitize_text(" ".join(_decorate_words(picked, punct, numbers, gen)))
        return _build_sentences_text(num_words, numbers, gen)
    if mode in ("quote", "passage", "passages"):
        t1, t2 = load_tiered_passages()
        pool = t1 + t2 if (t1 or t2) else _load_quotes()
        if not pool:
            raise ValueError("no quotes or passages found")
        return sanitize_text(gen.choice(pool))
    if mode == "code":
        return sanitize_text(gen.choice(_load_code_chunks(language)))
    raise ValueError(f"unknown mode {mode!r}")
