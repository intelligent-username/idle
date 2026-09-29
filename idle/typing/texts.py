"""Word, quote, and code text builders."""

import random
from pathlib import Path

PUNCT_MARKS: tuple[str, ...] = (".", ",", ";", ":", "!", "?")

_SNIPPET_SEP = "# ---"


def _read_data_file(relative: str) -> str:
    """Read text file from idle package data."""
    try:
        from importlib import resources

        ref = resources.files("idle").joinpath(relative)
        return ref.read_text(encoding="utf-8")
    except (FileNotFoundError, ModuleNotFoundError, NotADirectoryError):
        base: Path = Path(__file__).resolve().parents[1]
        return (base / relative).read_text(encoding="utf-8")


def load_words(n: int) -> list[str]:
    """Load word list with n entries."""
    raw: str = _read_data_file(f"data/words_{n}.txt")
    words: list[str] = [line.strip() for line in raw.splitlines()]
    return [w for w in words if w]


def _load_quotes() -> list[str]:
    """Load non-empty quote lines."""
    raw: str = _read_data_file("data/quotes.txt")
    lines: list[str] = [line.strip() for line in raw.splitlines()]
    return [line for line in lines if line]


def _load_code_chunks(language: str) -> list[str]:
    """Load code chunks for language.

    Test: chunks = _load_code_chunks("python")
    gives len(chunks) >= 20 with "def" in
    " ".join(chunks).
    """
    if language != "python":
        raise ValueError(f"unsupported language {language!r}")
    raw: str = _read_data_file("data/snippets/python.txt")
    parts: list[str] = [p.strip("\n") for p in raw.split(_SNIPPET_SEP)]
    chunks: list[str] = [p.strip() for p in parts if p.strip()]
    if not chunks:
        raise ValueError("no code snippets found")
    return chunks


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
    """Build test text for mode.

    Test: make_text("words", words=["hi","yo"],
    num_words=2, rng=Random(0)) returns two
    space-joined tokens from the given list.
    """
    gen: random.Random = rng if rng is not None else random.Random()
    if mode in ("time", "words"):
        source: list[str] = words if words is not None else load_words(word_list)
        if not source:
            raise ValueError("empty word source")
        picked: list[str] = [gen.choice(source) for _ in range(num_words)]
        return " ".join(_decorate_words(picked, punct, numbers, gen))
    if mode == "quote":
        quotes: list[str] = _load_quotes()
        if not quotes:
            raise ValueError("no quotes found")
        return gen.choice(quotes)
    if mode == "code":
        chunks: list[str] = _load_code_chunks(language)
        return gen.choice(chunks)
    raise ValueError(f"unknown mode {mode!r}")
