"""Cookie auth storage and header building."""

import json
import os
from pathlib import Path


def _auth_path() -> Path:
    """Return auth file path, ensuring parent dirs."""
    from idle.config import resolve_paths

    _, _, auth_path = resolve_paths()
    return auth_path


def save_auth(cookies: dict[str, str]) -> None:
    """Save cookies to auth file with 0600 perms."""
    path: Path = _auth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data: str = json.dumps(cookies)
    path.write_text(data, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_auth() -> dict[str, str] | None:
    """Load saved cookies, return None when missing."""
    path: Path = _auth_path()
    if not path.exists():
        return None
    try:
        raw: str = path.read_text(encoding="utf-8")
        data: object = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(key, str) and isinstance(value, str):
            out[key] = value
    return out if out else None


def auth_headers() -> dict[str, str]:
    """Build Cookie, csrf, and Referer headers."""
    cookies: dict[str, str] | None = load_auth()
    headers: dict[str, str] = {
        "Referer": "https://leetcode.com/",
        "User-Agent": "idle-lc/0.1",
    }
    if not cookies:
        return headers
    parts: list[str] = [f"{k}={v}" for k, v in cookies.items()]
    headers["Cookie"] = "; ".join(parts)
    token: str = cookies.get("csrftoken", "") or cookies.get("csrf", "")
    if token:
        headers["x-csrftoken"] = token
        headers["X-CSRFToken"] = token
    return headers


def is_expired(resp_status: int, body: str) -> bool:
    """Detect expired login from status or body."""
    if resp_status in (401, 403):
        return True
    low: str = body.lower()
    markers: tuple[str, ...] = (
        "/accounts/login",
        "please login",
        "please log in",
        "login to continue",
        "not authenticated",
    )
    for marker in markers:
        if marker in low:
            return True
    return False
