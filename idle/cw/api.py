"""Codewars REST API client and kata catalog."""

from datetime import date
import json
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

from idle.cw.auth import auth_headers

BASE_URL: str = "https://www.codewars.com/api/v1"

# Curated catalog of well-known katas spanning 8 kyu (beginner) to 1 kyu (expert)
CURATED_KATAS: list[dict[str, Any]] = [
    # 8 kyu
    {
        "id": "50654ddff44f800200000007",
        "slug": "multiply",
        "name": "Multiply",
        "rank": {"id": -8, "name": "8 kyu", "color": "white"},
        "tags": ["Fundamentals"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "53da3dbb4a5168369a0000fe",
        "slug": "even-or-odd",
        "name": "Even or Odd",
        "rank": {"id": -8, "name": "8 kyu", "color": "white"},
        "tags": ["Fundamentals", "Mathematics"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "56dec885c54a926dcd001095",
        "slug": "opposite-number",
        "name": "Opposite number",
        "rank": {"id": -8, "name": "8 kyu", "color": "white"},
        "tags": ["Fundamentals"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "5168bb5dfe9a00b126000018",
        "slug": "reversed-strings",
        "name": "Reversed Strings",
        "rank": {"id": -8, "name": "8 kyu", "color": "white"},
        "tags": ["Strings", "Fundamentals"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "5715eaedb436cf5606000381",
        "slug": "sum-of-positive",
        "name": "Sum of positive",
        "rank": {"id": -8, "name": "8 kyu", "color": "white"},
        "tags": ["Arrays", "Fundamentals"],
        "languages": ["python", "javascript"],
    },
    # 7 kyu
    {
        "id": "54ff3102c1bad923760001f3",
        "slug": "vowel-count",
        "name": "Vowel Count",
        "rank": {"id": -7, "name": "7 kyu", "color": "white"},
        "tags": ["Strings", "Fundamentals"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "52fba66badcd10859f00097e",
        "slug": "disemvowel-trolls",
        "name": "Disemvowel Trolls",
        "rank": {"id": -7, "name": "7 kyu", "color": "white"},
        "tags": ["Strings", "Regular Expressions"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "546e2562b03326a88e000020",
        "slug": "square-every-digit",
        "name": "Square Every Digit",
        "rank": {"id": -7, "name": "7 kyu", "color": "white"},
        "tags": ["Mathematics", "Fundamentals"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "554b4ac871d6813a03000035",
        "slug": "highest-and-lowest",
        "name": "Highest and Lowest",
        "rank": {"id": -7, "name": "7 kyu", "color": "white"},
        "tags": ["Fundamentals", "Strings"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "5467e4d82edf8bbf40000155",
        "slug": "descending-order",
        "name": "Descending Order",
        "rank": {"id": -7, "name": "7 kyu", "color": "white"},
        "tags": ["Fundamentals"],
        "languages": ["python", "javascript"],
    },
    # 6 kyu
    {
        "id": "514b92a657cdc65150000006",
        "slug": "multiples-of-3-or-5",
        "name": "Multiples of 3 or 5",
        "rank": {"id": -6, "name": "6 kyu", "color": "yellow"},
        "tags": ["Algorithms", "Mathematics"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "5266876b8f4bf2da9b000362",
        "slug": "who-likes-it",
        "name": "Who likes it?",
        "rank": {"id": -6, "name": "6 kyu", "color": "yellow"},
        "tags": ["Strings", "Fundamentals"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "525f50e3b73515a6db000b83",
        "slug": "create-phone-number",
        "name": "Create Phone Number",
        "rank": {"id": -6, "name": "6 kyu", "color": "yellow"},
        "tags": ["Arrays", "Strings"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "5277c8a221e209d3f6000b56",
        "slug": "valid-braces",
        "name": "Valid Braces",
        "rank": {"id": -6, "name": "6 kyu", "color": "yellow"},
        "tags": ["Algorithms", "Data Structures"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "5526fc09a1bbd946250002dc",
        "slug": "find-the-parity-outlier",
        "name": "Find The Parity Outlier",
        "rank": {"id": -6, "name": "6 kyu", "color": "yellow"},
        "tags": ["Algorithms"],
        "languages": ["python", "javascript"],
    },
    # 5 kyu
    {
        "id": "52597aa56021e91c93000cb0",
        "slug": "moving-zeros-to-the-end",
        "name": "Moving Zeros To The End",
        "rank": {"id": -5, "name": "5 kyu", "color": "yellow"},
        "tags": ["Arrays", "Algorithms", "Sorting"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "520b9d2db5c08804100000dd",
        "slug": "simple-pig-latin",
        "name": "Simple Pig Latin",
        "rank": {"id": -5, "name": "5 kyu", "color": "yellow"},
        "tags": ["Regular Expressions", "Algorithms"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "52685f7382004e774f0001f7",
        "slug": "human-readable-time",
        "name": "Human Readable Time",
        "rank": {"id": -5, "name": "5 kyu", "color": "yellow"},
        "tags": ["Date Time", "Mathematics", "Algorithms"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "530e15517bc88ac656000716",
        "slug": "rot13-1",
        "name": "Rot13",
        "rank": {"id": -5, "name": "5 kyu", "color": "yellow"},
        "tags": ["Ciphers", "Fundamentals"],
        "languages": ["python", "javascript"],
    },
    # 4 kyu
    {
        "id": "51c8e37ee245da32ff000055",
        "slug": "strip-comments",
        "name": "Strip Comments",
        "rank": {"id": -4, "name": "4 kyu", "color": "blue"},
        "tags": ["Strings", "Algorithms"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "521c2db8ddc89b9b7a0000c1",
        "slug": "snail",
        "name": "Snail",
        "rank": {"id": -4, "name": "4 kyu", "color": "blue"},
        "tags": ["Arrays", "Algorithms"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "51ba717bb08c1cd60f00002f",
        "slug": "range-extraction",
        "name": "Range Extraction",
        "rank": {"id": -4, "name": "4 kyu", "color": "blue"},
        "tags": ["Algorithms", "Strings"],
        "languages": ["python", "javascript"],
    },
    # 3 kyu
    {
        "id": "54388a032d8f5c4f56000624",
        "slug": "battleship-field-validator",
        "name": "Battleship field validator",
        "rank": {"id": -3, "name": "3 kyu", "color": "blue"},
        "tags": ["Algorithms", "Data Structures"],
        "languages": ["python", "javascript"],
    },
    {
        "id": "534e01fbbb17187c7e0000c6",
        "slug": "make-a-spiral",
        "name": "Make a spiral",
        "rank": {"id": -3, "name": "3 kyu", "color": "blue"},
        "tags": ["Algorithms", "Control Flow"],
        "languages": ["python", "javascript"],
    },
]


def _cache_path() -> Path:
    from idle.config import resolve_paths

    _, _, auth_path = resolve_paths()
    return auth_path.parent / "cw_cache.json"


def fetch_user(username: str) -> dict[str, Any]:
    """Fetch user profile and stats from Codewars API."""
    url: str = f"{BASE_URL}/users/{username}"
    req = urllib.request.Request(url, headers=auth_headers())
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def fetch_completed(username: str, page: int = 0) -> list[dict[str, Any]]:
    """Fetch list of completed challenges for a given user."""
    url: str = f"{BASE_URL}/users/{username}/code-challenges/completed?page={page}"
    req = urllib.request.Request(url, headers=auth_headers())
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
            return data.get("data", [])
    except (urllib.error.HTTPError, urllib.error.URLError):
        return []


def fetch_kata(id_or_slug: str) -> dict[str, Any]:
    """Fetch kata detail from Codewars API, or load from cache."""
    url: str = f"{BASE_URL}/code-challenges/{id_or_slug}"
    req = urllib.request.Request(url, headers=auth_headers())
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
            _update_cache([data])
            return data
    except urllib.error.HTTPError as exc:
        # Check if we have it cached locally
        cached = _get_cached_kata(id_or_slug)
        if cached:
            return cached
        raise RuntimeError(f"Kata '{id_or_slug}' not found (HTTP {exc.code})") from exc
    except (urllib.error.URLError, OSError) as exc:
        cached = _get_cached_kata(id_or_slug)
        if cached:
            return cached
        raise RuntimeError("Could not connect to Codewars (offline?).") from exc


def _get_cached_kata(id_or_slug: str) -> dict[str, Any] | None:
    cache = _load_cache()
    for item in cache:
        if item.get("id") == id_or_slug or item.get("slug") == id_or_slug:
            return item
    for item in CURATED_KATAS:
        if item.get("id") == id_or_slug or item.get("slug") == id_or_slug:
            return item
    return None


def _load_cache() -> list[dict[str, Any]]:
    path = _cache_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return []


def _update_cache(katas: list[dict[str, Any]]) -> None:
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _load_cache()
    by_id = {k["id"]: k for k in existing if "id" in k}
    for k in katas:
        if "id" in k:
            by_id[k["id"]] = k
    try:
        path.write_text(json.dumps(list(by_id.values()), indent=2), encoding="utf-8")
    except OSError:
        pass


def fetch_kata_list(username: str = "", refresh: bool = False) -> list[dict[str, Any]]:
    """Return catalog of katas with solved status for user."""
    completed_ids: set[str] = set()
    if username:
        completed = fetch_completed(username)
        completed_ids = {c.get("id", "") for c in completed}

    cached = _load_cache()
    combined = {k["id"]: dict(k) for k in CURATED_KATAS}
    for k in cached:
        if "id" in k:
            combined[k["id"]] = dict(k)

    result: list[dict[str, Any]] = []
    for k_id, item in combined.items():
        entry = dict(item)
        entry["status"] = "ac" if k_id in completed_ids else "todo"
        result.append(entry)

    # Sort by rank difficulty (-8 to -1) then name
    def sort_key(k: dict[str, Any]) -> tuple[int, str]:
        rank_obj = k.get("rank") or {}
        r_id = rank_obj.get("id", -8)
        return (r_id, k.get("name", ""))

    result.sort(key=sort_key)
    return result


def fetch_daily() -> dict[str, Any]:
    """Pick deterministic daily kata based on day of year."""
    today = date.today()
    day_idx = (today.year * 365 + today.timetuple().tm_yday) % len(CURATED_KATAS)
    chosen = CURATED_KATAS[day_idx]
    try:
        return fetch_kata(chosen["slug"])
    except RuntimeError:
        return chosen
