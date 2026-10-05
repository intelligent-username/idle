"""Data loaders, passage sets, and sanitize utilities for typing texts."""

import re
from pathlib import Path

__all__: list[str] = [
    "_CUSTOM_NUM_PASSAGES",
    "_LEVEL5_MEANINGFUL_TEXTS",
    "_NON_CUSTOM_NUM_PASSAGES",
    "_SNIPPET_SEP",
    "_load_code_chunks",
    "_load_passages",
    "_load_quotes",
    "_read_data_file",
    "load_tiered_passages",
    "load_words",
    "rate_passage",
    "sanitize_text",
]

_SNIPPET_SEP: str = "# ---"

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
    """Normalize quotes, dashes, whitespace and strip unprintable characters."""
    repl = {
        "“": '"', "”": '"', "„": '"', "‘": "'", "’": "'",
        "—": " - ", "–": "-", "…": "...", "\u00a0": " ",
        "\t": " ", "\r": " ", "\n": " ",
    }
    for old, new in repl.items():
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
    return [w.strip() for w in raw.splitlines() if w.strip()]


def _load_quotes() -> list[str]:
    """Load non-empty quote lines."""
    raw: str = _read_data_file("data/quotes.txt")
    return [line.strip() for line in raw.splitlines() if line.strip()]


_PASSAGE_FILES: tuple[str, ...] = (
    "af.txt", "Clemens.txt", "CaP.txt", "nfu.txt", "totc.txt", "CaP", "Clemens",
)


def _load_passages() -> list[str]:
    """Load literary passages and quotes, sanitized into clean paragraphs."""
    passages: list[str] = []
    seen: set[str] = set()
    for name in _PASSAGE_FILES:
        try:
            raw = _read_data_file(f"data/passages/{name}")
            for p in (p.strip() for p in raw.split("\n\n") if p.strip()):
                cleaned = sanitize_text(p)
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    passages.append(cleaned)
        except (OSError, ValueError):
            pass
    try:
        for q in _load_quotes():
            cleaned = sanitize_text(q)
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                passages.append(cleaned)
    except (OSError, ValueError):
        pass
    return passages


def rate_passage(text: str) -> int:
    """Rate passage difficulty: 1 for Medium, 2 for Hard."""
    clean = sanitize_text(text)
    words = clean.split()
    if not words:
        return 1
    has_complex_punct = any(ch in clean for ch in (";", ":", "(", ")", '"')) or "..." in clean
    letters_only = [re.sub(r"[^a-zA-Z]", "", w) for w in words]
    long_words = sum(1 for w in letters_only if len(w) >= 9)
    long_ratio = long_words / len(words)
    rare_letters = sum(1 for ch in clean.lower() if ch in ("j", "q", "x", "z"))
    rare_ratio = rare_letters / len(clean)
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
    chunks = [p.strip() for p in raw.split(_SNIPPET_SEP) if p.strip()]
    if not chunks:
        raise ValueError("no code snippets found")
    return chunks
