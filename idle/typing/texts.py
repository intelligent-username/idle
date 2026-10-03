import random
import re
from pathlib import Path

PUNCT_MARKS: tuple[str, ...] = (".", ",", ";", ":", "!", "?")

_SNIPPET_SEP = "# ---"

_NON_CUSTOM_NUM_PASSAGES: tuple[str, ...] = (
    "On July 20, 1969, the Apollo 11 lunar module touched down on the Moon with only 30 seconds of fuel remaining. Commander Neil Armstrong radioed Houston at 20:17 UTC, watched live by an estimated 650 million viewers across 47 countries.",
    "The marathon distance was standardized at 42.195 kilometers, or exactly 26 miles and 385 yards, during the 1908 Olympic Games in London so that the race would conclude in front of the Royal Box at White City Stadium.",
    "Between 1775 and 1783, over 217,000 soldiers served in the Continental Army. General George Washington led 17 major engagements, securing victory at Yorktown on October 19, 1781 after a 21-day siege.",
    "The speed of light in a vacuum is defined as exactly 299,792,458 meters per second, which equates to roughly 186,282 miles per second. At this velocity, sunlight reaches Earth in 8 minutes and 20 seconds across 93 million miles.",
    "In 1859, Charles Darwin published On the Origin of Species with an initial print run of 1,250 copies, priced at 15 shillings each, which sold out on the first day of release on November 24.",
    "Mount Everest stands at an official elevation of 8,848.86 meters above sea level, approximately 29,031.7 feet. Temperatures near the summit routinely drop to minus 36 degrees Celsius with winds exceeding 175 kilometers per hour.",
    "In 1775, there were a king with a large jaw and a queen with a plain face on the throne of England. Mrs. Southcott had recently attained her 25th birthday, while the Cock-lane ghost had been laid only 12 years prior.",
)

_CUSTOM_NUM_PASSAGES: tuple[str, ...] = (
    "Cluster node-04 reported 1,024 active TCP connections with an average round-trip latency of 14.8 milliseconds and 99.98% reliability over 48 consecutive hours of load testing.",
    "During the Q4 sprint, the engineering team closed 142 pull requests, reduced memory consumption from 850 MB to 320 MB, and improved throughput by 45% across all 12 microservices.",
    "The automated trading algorithm processed 7,850 orders per second, maintaining slippage below 0.05% across 3 global exchanges between 09:30 and 16:00 EST.",
    "Telemetry data indicated vehicle 57 traveled 412 miles at an average speed of 68.4 mph, consuming 11.2 gallons of fuel for an overall efficiency rating of 36.8 miles per gallon.",
    "The database migration script migrated 2,450,000 user records into 64 shards within 38 minutes, achieving a zero-error rate across 100% of validated schemas.",
    "Flight DL408 climbed to cruising altitude of 36,000 feet at 510 knots ground speed, carrying 164 passengers and 4,800 pounds of cargo on a 4-hour flight.",
    "The laboratory analyzed 250 clinical blood samples across 5 distinct control groups, recording internal temperatures between 36.5 and 37.2 degrees Celsius over 72 consecutive hours.",
    "In fiscal year 2023, the charitable endowment distributed $14.5 million across 87 community initiatives, directly benefiting over 120,000 students in 42 public school districts.",
)

_LEVEL5_MEANINGFUL_TEXTS: tuple[str, ...] = (
    "Configure `api_key` in config.toml (port: 8080, host: '127.0.0.1'); verify HTTP/2 status code 200 OK via curl -X POST!",
    "The hypothesis (p < 0.001, 95% CI [12.4, 18.9]) confirmed that user-experience scores improved by +34.8% after the v2.1.0 update.",
    "According to Section 4(b), employees must submit Form W-2 & 1099-MISC before 04/15/2025; late filings incur a $50/month penalty!",
    "Query: SELECT user_id, COUNT(*) AS total_runs FROM tests WHERE latency_ms <= 250.0 GROUP BY user_id ORDER BY total_runs DESC;",
    "The asynchronous micro-service returned 'status': 'SUCCESS' with payload={id: 994, retries: 3, elapsed: 0.042s}.",
    "Specialized algorithms--like A* search (heuristic: h(n) <= c(n, p))--solve 100% of grid navigation problems in O(b^d) time.",
    "Package version ^3.14.0 requires: python>=3.11, torch>=2.0.1, & numpy!=1.24.0; install with: `uv pip install -r requirements.txt`.",
    "Review items #101-#105: check (a) SSL/TLS 1.3 handshakes, (b) HMAC-SHA256 signatures, and (c) OAuth2 tokens in Authorization headers.",
    "Run `pytest -v -k 'test_auth and not slow'` with ENV_VAR='staging_2026' & DB_URL='postgres://user:p@ss@localhost:5432/test_db'!",
    "Yield was calculated as: [Total_Units * (1 - Defect_Rate)] / Hours_Worked; e.g., [1,200 * (1 - 0.025)] / 40.0 = 29.25 units/hr.",
    "Warning (code #E409): DNS lookup failed for sub-domain `api.v3.service-mesh.internal:9443` [IPv6: 2001:db8::1] after 3 retries!",
    "The quick, nimble brown fox jumped over 10 lazy dogs @ midnight (#midnight-run), then sprinted 100m in 9.58s [record]!",
    "Matrix dimensions M[i][j] = (alpha * 3.1415) / (beta + 1.0); assert M.shape == (512, 1024), f'Error: {M.shape} != expected'!",
    "Discount code 'SAVE_25%' applied: Subtotal = $149.99 - $37.50 + $8.25 tax = $120.74 (Saved: 25.0%).",
)


def sanitize_text(text: str) -> str:
    """Normalize quotes, dashes, whitespace and strip weird characters."""
    replacements: dict[str, str] = {
        "“": '"',
        "”": '"',
        "„": '"',
        "‘": "'",
        "’": "'",
        "—": " - ",
        "–": "-",
        "…": "...",
        "\u00a0": " ",
        "\t": " ",
        "\r": " ",
        "\n": " ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = "".join(ch for ch in text if 32 <= ord(ch) <= 126)
    return re.sub(r"\s+", " ", text).strip()


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


_PASSAGE_FILES: tuple[str, ...] = (
    "af.txt",
    "Clemens.txt",
    "CaP.txt",
    "nfu.txt",
    "totc.txt",
    "CaP",
    "Clemens",
)


def _load_passages() -> list[str]:
    """Load literary passages and quotes, sanitized into clean paragraphs."""
    passages: list[str] = []
    seen: set[str] = set()
    for name in _PASSAGE_FILES:
        try:
            raw = _read_data_file(f"data/passages/{name}")
            paras = [p.strip() for p in raw.split("\n\n") if p.strip()]
            for p in paras:
                cleaned = sanitize_text(p)
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    passages.append(cleaned)
        except (OSError, ValueError):
            pass
    try:
        quotes = _load_quotes()
        for q in quotes:
            cleaned = sanitize_text(q)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                passages.append(cleaned)
    except (OSError, ValueError):
        pass
    return passages


def rate_passage(text: str) -> int:
    """Rate passage difficulty: 1 for Medium, 2 for Hard.

    Tier 1 (Medium): Accessible vocabulary, straightforward structure, standard punctuation.
    Tier 2 (Hard): Complex punctuation (semicolons, colons, parentheses, dialog quotes,
    ellipses, dashes), archaic or specialized vocabulary, and long multi-clause sentences.
    """
    clean = sanitize_text(text)
    words = clean.split()
    if not words:
        return 1

    # Tier 2 indicators:
    # 1. Complex punctuation: ;, :, (, ), ", ...
    has_complex_punct = any(ch in clean for ch in (";", ":", "(", ")", '"')) or "..." in clean

    # 2. Advanced vocabulary and word complexity
    letters_only = [re.sub(r"[^a-zA-Z]", "", w) for w in words]
    long_words = sum(1 for w in letters_only if len(w) >= 9)
    long_ratio = long_words / len(words)
    rare_letters = sum(1 for ch in clean.lower() if ch in ("j", "q", "x", "z"))
    rare_ratio = rare_letters / len(clean)

    # 3. Sentence complexity (very long sentences)
    sentences = [s.strip() for s in re.split(r"[.!?]+", clean) if s.strip()]
    max_sentence_len = max((len(s.split()) for s in sentences), default=0)

    if has_complex_punct or long_ratio >= 0.08 or rare_ratio >= 0.015 or max_sentence_len >= 35:
        return 2
    return 1


def load_tiered_passages() -> tuple[list[str], list[str]]:
    """Load passages split into Tier 1 (Medium) and Tier 2 (Hard)."""
    tier1: list[str] = []
    tier2: list[str] = []
    for p in _load_passages():
        if rate_passage(p) == 1:
            tier1.append(p)
        else:
            tier2.append(p)
    return tier1, tier2



def _load_code_chunks(language: str) -> list[str]:
    """Load code chunks for language."""
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


def _build_sentences_text(num_words: int, numbers: bool, gen: random.Random) -> str:
    """Combine realistic sentences until target word count is satisfied."""
    quotes = _load_quotes()
    if not quotes:
        quotes = ["The quick brown fox jumps over the lazy dog."]
    shuffled = list(quotes)
    gen.shuffle(shuffled)
    selected: list[str] = []
    word_count = 0
    idx = 0
    while word_count < num_words and idx < len(shuffled) * 4:
        sentence = shuffled[idx % len(shuffled)]
        selected.append(sentence)
        word_count += len(sentence.split())
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
    if not passages:
        passages = ["The quick brown fox jumps over the lazy dog."]
    p = gen.choice(passages)
    words = p.split()
    if len(words) <= num_words + 10:
        return p
    # Split by sentences to get natural sentence-bounded snippets
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
    snippet = " ".join(accum)
    return sanitize_text(snippet)


def build_difficulty_typing_text(
    difficulty: int,
    num_words: int = 50,
    rng: random.Random | None = None,
) -> str:
    """Build typing test text according to 5 difficulty tiers.

    1 (0): Really easy, common words randomly, lowercase letters only.
    2 (1): Medium difficulty words with capitalizations.
    3 (2): Passages varying by length, snippets of passages.
    4 (3): Harder passages with numbers (custom-written and non-custom).
    5 (4): Meaningful sentences with uppercase/lowercase, numbers, special characters.
    """
    gen: random.Random = rng if rng is not None else random.Random()
    diff = max(0, min(difficulty, 4))

    if diff == 0:
        # Easy: common lowercase words, no caps, no punctuation, letters only
        words_200 = load_words(200)
        clean_words = [
            re.sub(r"[^a-z]", "", w.lower()) for w in words_200 if re.sub(r"[^a-z]", "", w.lower())
        ]
        chosen = [gen.choice(clean_words) for _ in range(num_words)]
        return sanitize_text(" ".join(chosen))

    if diff == 1:
        # Medium: medium difficulty words with capitalizations
        words_1000 = load_words(1000)
        clean_words = [
            re.sub(r"[^a-zA-Z]", "", w) for w in words_1000 if re.sub(r"[^a-zA-Z]", "", w)
        ]
        chosen = [gen.choice(clean_words).capitalize() for _ in range(num_words)]
        return sanitize_text(" ".join(chosen))

    if diff == 2:
        # Hard: passages and snippets of passages varying by length (Tier 2 hard passages)
        tier1, tier2 = load_tiered_passages()
        chosen_pool = tier2 if tier2 else (tier1 or _load_passages())
        target_len = max(20, min(num_words, 80))
        return _get_passage_snippet(chosen_pool, target_len, gen)

    if diff == 3:
        # Expert: harder passages with numbers (custom-written + non-custom)
        candidates = list(_NON_CUSTOM_NUM_PASSAGES) + list(_CUSTOM_NUM_PASSAGES)
        p = gen.choice(candidates)
        words = p.split()
        if len(words) > num_words + 15:
            sentences = re.split(r"(?<=[.!?])\s+", p)
            accum: list[str] = []
            curr_len = 0
            for s in sentences:
                accum.append(s)
                curr_len += len(s.split())
                if curr_len >= num_words:
                    break
            return sanitize_text(" ".join(accum))
        return sanitize_text(p)

    # Master (4): meaningful sentences with mixed case, numbers, and symbols
    chosen_sentences: list[str] = []
    shuffled = list(_LEVEL5_MEANINGFUL_TEXTS)
    gen.shuffle(shuffled)
    total_words = 0
    idx = 0
    while total_words < num_words and idx < len(shuffled) * 2:
        sent = shuffled[idx % len(shuffled)]
        chosen_sentences.append(sent)
        total_words += len(sent.split())
        idx += 1
    return sanitize_text(" ".join(chosen_sentences))


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
            picked: list[str] = [gen.choice(words) for _ in range(num_words)]
            return sanitize_text(" ".join(_decorate_words(picked, punct, numbers, gen)))
        return _build_sentences_text(num_words, numbers, gen)
    if mode in ("quote", "passage", "passages"):
        tier1, tier2 = load_tiered_passages()
        pool = tier1 + tier2 if (tier1 or tier2) else _load_quotes()
        if not pool:
            raise ValueError("no quotes or passages found")
        return sanitize_text(gen.choice(pool))
    if mode == "code":
        chunks: list[str] = _load_code_chunks(language)
        return sanitize_text(gen.choice(chunks))
    raise ValueError(f"unknown mode {mode!r}")


