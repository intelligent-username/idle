"""Cookie auth storage and header building."""

import json
import os
from pathlib import Path
from typing import Any

BROWSER_UA: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


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
        "Origin": "https://leetcode.com",
        "User-Agent": BROWSER_UA,
        "X-Requested-With": "XMLHttpRequest",
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
        "unauthorized",
        "session expired",
        "csrf",
        "invalid session",
    )
    for marker in markers:
        if marker in low:
            return True
    return False


def is_challenge(body: str) -> bool:
    """Detect Cloudflare or captcha challenge page."""
    low: str = body.lower()
    markers: tuple[str, ...] = (
        "__cf_bm",
        "cf_clearance",
        "just a moment",
        "attention required",
        "verify you are human",
        "verify human",
        "captcha",
        "cloudflare",
    )
    for marker in markers:
        if marker in low:
            return True
    return False


def _cookies_from_jar(jar: Any) -> dict[str, str]:
    """Collect cookie name to value mapping."""
    out: dict[str, str] = {}
    for cookie in jar:
        name: str = str(getattr(cookie, "name", ""))
        if name:
            out[name] = str(getattr(cookie, "value", ""))
    return out


def _extract_csrf_token(html: str, fallback: str) -> str:
    """Extract csrfmiddlewaretoken from login page HTML."""
    import re

    match = re.search(r'name="csrfmiddlewaretoken"[^>]*value="([^"]+)"', html)
    if match:
        return str(match.group(1))
    alt = re.search(r'value="([^"]+)"[^>]*name="csrfmiddlewaretoken"', html)
    if alt:
        return str(alt.group(1))
    return fallback


def _fetch_login_page(opener: Any, login_url: str) -> str:
    """Fetch login page HTML via opener."""
    import urllib.request

    req = urllib.request.Request(
        login_url,
        headers={"User-Agent": BROWSER_UA, "Referer": "https://leetcode.com/"},
    )
    try:
        with opener.open(req, timeout=10) as resp:
            return str(resp.read().decode("utf-8", "replace"))
    except OSError as exc:
        raise RuntimeError("could not login (offline?). Check network and retry.") from exc


def _submit_login_form(
    opener: Any, login_url: str, token: str, username: str, password: str
) -> str:
    """Submit login form, return response body text."""
    import urllib.parse
    import urllib.request

    payload = urllib.parse.urlencode(
        {"csrfmiddlewaretoken": token, "login": username, "password": password}
    ).encode()
    req = urllib.request.Request(
        login_url,
        data=payload,
        headers={
            "Referer": "https://leetcode.com/accounts/login/",
            "Origin": "https://leetcode.com",
            "User-Agent": BROWSER_UA,
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        with opener.open(req, timeout=10) as resp:
            return str(resp.read().decode("utf-8", "replace"))
    except OSError as exc:
        raise RuntimeError("could not login (offline?). Check network and retry.") from exc


def login_username_password(username: str, password: str) -> dict[str, str]:
    """Login with username and password, return session cookies.

    >>> callable(login_username_password)
    True
    """
    import http.cookiejar
    import urllib.request

    if not username or not password:
        raise RuntimeError("login failed: bad credentials or captcha")
    login_url: str = "https://leetcode.com/accounts/login/"
    jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    html: str = _fetch_login_page(opener, login_url)
    if is_challenge(html):
        raise RuntimeError("LeetCode challenge detected (captcha/cloudflare). Retry later.")
    token: str = _extract_csrf_token(html, _cookies_from_jar(jar).get("csrftoken", ""))
    if not token:
        raise RuntimeError("could not login (offline?). Check network and retry.")
    body: str = _submit_login_form(opener, login_url, token, username, password)
    if is_challenge(body):
        raise RuntimeError("LeetCode challenge detected (captcha/cloudflare). Retry later.")
    cookies: dict[str, str] = _cookies_from_jar(jar)
    session: str = cookies.get("LEETCODE_SESSION", "")
    csrf: str = cookies.get("csrftoken", "")
    if not session or not csrf:
        raise RuntimeError("login failed: bad credentials or captcha")
    return {"LEETCODE_SESSION": session, "csrftoken": csrf}
