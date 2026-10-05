"""Cookie auth storage and header building."""

import json
import os
from pathlib import Path
from typing import Any

BROWSER_UA: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    " (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


def load_dotenv() -> dict[str, str]:
    """Parse .env file in cwd or project root into dict."""
    env_vars: dict[str, str] = {}
    candidates: list[Path] = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent / ".env",
        Path(__file__).resolve().parents[1] / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for path in candidates:
        if path.is_file():
            try:
                content = path.read_text(encoding="utf-8")
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    if key and key not in env_vars:
                        env_vars[key] = val
            except OSError:
                pass
    return env_vars


def get_env_credentials() -> tuple[str, str]:
    """Return (username, password) from environment or .env file."""
    env: dict[str, str] = load_dotenv()
    username: str = (
        os.environ.get("LC_USERNAME")
        or os.environ.get("LEETCODE_USERNAME")
        or env.get("LC_USERNAME")
        or env.get("LEETCODE_USERNAME")
        or ""
    )
    password: str = (
        os.environ.get("LC_PW")
        or os.environ.get("LC_PASSWORD")
        or os.environ.get("LEETCODE_PASSWORD")
        or env.get("LC_PW")
        or env.get("LC_PASSWORD")
        or env.get("LEETCODE_PASSWORD")
        or ""
    )
    return (username, password)


def get_env_session() -> tuple[str, str]:
    """Return (session, csrf) from environment or .env file if present."""
    env: dict[str, str] = load_dotenv()
    session: str = (
        os.environ.get("LEETCODE_SESSION")
        or os.environ.get("LC_SESSION")
        or env.get("LEETCODE_SESSION")
        or env.get("LC_SESSION")
        or ""
    )
    csrf: str = (
        os.environ.get("csrftoken")
        or os.environ.get("LC_CSRF")
        or os.environ.get("CSRFTOKEN")
        or env.get("csrftoken")
        or env.get("LC_CSRF")
        or env.get("CSRFTOKEN")
        or ""
    )
    return (session, csrf)


def load_saved_credentials() -> tuple[str, str]:
    """Return (username, password) from auth.json if previously saved, else from .env."""
    path: Path = _auth_path()
    if path.exists():
        try:
            raw: str = path.read_text(encoding="utf-8")
            data: Any = json.loads(raw)
            if isinstance(data, dict):
                u: str = str(data.get("username", ""))
                p: str = str(data.get("password", ""))
                if u or p:
                    return (u, p)
        except (OSError, ValueError):
            pass
    return get_env_credentials()


def _auth_path() -> Path:
    """Return auth file path, ensuring parent dirs."""
    from idle.config import resolve_paths

    _, _, auth_path = resolve_paths()
    return auth_path


def save_auth(
    cookies: dict[str, str], username: str = "", password: str = ""
) -> None:
    """Save cookies and optional credentials to auth file with 0600 perms."""
    path: Path = _auth_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            raw: str = path.read_text(encoding="utf-8")
            loaded: Any = json.loads(raw)
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, ValueError):
            pass
    payload: dict[str, Any] = dict(existing)
    for k, v in cookies.items():
        payload[k] = v
    payload["cookies"] = dict(cookies)
    if username:
        payload["username"] = username
    if password:
        payload["password"] = password
    data: str = json.dumps(payload)
    path.write_text(data, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_auth() -> dict[str, str] | None:
    """Load saved cookies, return None when missing."""
    path: Path = _auth_path()
    if not path.exists():
        sess, csrf = get_env_session()
        if sess:
            out: dict[str, str] = {"LEETCODE_SESSION": sess}
            if csrf:
                out["csrftoken"] = csrf
            return out
        return None
    try:
        raw: str = path.read_text(encoding="utf-8")
        data: object = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    cookies_dict: Any = data.get("cookies")
    if isinstance(cookies_dict, dict):
        out_c: dict[str, str] = {
            str(k): str(v)
            for k, v in cookies_dict.items()
            if isinstance(k, str) and isinstance(v, str)
        }
        if out_c:
            return out_c
    out: dict[str, str] = {}
    for key, value in data.items():
        if (
            key not in ("username", "password", "cookies")
            and isinstance(key, str)
            and isinstance(value, str)
        ):
            out[key] = value
    if not out:
        sess, csrf = get_env_session()
        if sess:
            out = {"LEETCODE_SESSION": sess}
            if csrf:
                out["csrftoken"] = csrf
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
    import urllib.error
    import urllib.request

    req = urllib.request.Request(
        login_url,
        headers={"User-Agent": BROWSER_UA, "Referer": "https://leetcode.com/"},
    )
    try:
        with opener.open(req, timeout=10) as resp:
            return str(resp.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        body: str = ""
        try:
            body = str(exc.read().decode("utf-8", "replace")[:8192])
        except (OSError, ValueError):
            body = ""
        if is_challenge(body):
            raise RuntimeError(
                "LeetCode challenge detected (captcha/cloudflare). Retry later."
            ) from exc
        raise RuntimeError(
            f"login failed: HTTP {exc.code} from LeetCode (retry later)."
        ) from exc
    except OSError as exc:
        raise RuntimeError("could not login (offline?). Check network and retry.") from exc


def _submit_login_form(
    opener: Any, login_url: str, token: str, username: str, password: str
) -> str:
    """Submit login form, return response body text."""
    import urllib.error
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
    except urllib.error.HTTPError as exc:
        body: str = ""
        try:
            body = str(exc.read().decode("utf-8", "replace")[:8192])
        except (OSError, ValueError):
            body = ""
        if is_challenge(body):
            raise RuntimeError(
                "LeetCode challenge detected (captcha/cloudflare). Retry later."
            ) from exc
        raise RuntimeError(
            f"login failed: HTTP {exc.code} from LeetCode (retry later)."
        ) from exc
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
        raise RuntimeError("login failed: could not find login token (page changed?)")
    body: str = _submit_login_form(opener, login_url, token, username, password)
    if is_challenge(body):
        raise RuntimeError("LeetCode challenge detected (captcha/cloudflare). Retry later.")
    cookies: dict[str, str] = _cookies_from_jar(jar)
    session: str = cookies.get("LEETCODE_SESSION", "")
    csrf: str = cookies.get("csrftoken", "")
    if not session or not csrf:
        raise RuntimeError("login failed: bad credentials or captcha")
    return {"LEETCODE_SESSION": session, "csrftoken": csrf}


def _validator_headers(cookies: dict[str, str]) -> dict[str, str]:
    """Build validation headers from cookies."""
    parts: list[str] = [f"{k}={v}" for k, v in cookies.items() if k and v]
    headers: dict[str, str] = {
        "Referer": "https://leetcode.com/",
        "Origin": "https://leetcode.com",
        "User-Agent": BROWSER_UA,
        "Content-Type": "application/json",
        "X-Requested-With": "XMLHttpRequest",
    }
    if parts:
        headers["Cookie"] = "; ".join(parts)
    token: str = cookies.get("csrftoken", "") or cookies.get("csrf", "")
    if token:
        headers["x-csrftoken"] = token
        headers["X-CSRFToken"] = token
    return headers


def _is_valid_session_payload(payload: object) -> bool:
    """Check GraphQL payload for authenticated user shape."""
    if not isinstance(payload, dict):
        return False
    data: object = payload.get("data")
    if not isinstance(data, dict):
        return False
    status: object = data.get("userStatus")
    if isinstance(status, dict):
        name: str = str(status.get("username") or "")
        if name and name.lower() not in ("anonymous", "none"):
            return True
        return bool(status.get("isSignedIn") is True)
    viewer: object = data.get("viewer")
    if isinstance(viewer, dict):
        return bool(str(viewer.get("username") or ""))
    return False


def _explain_http_error(exc: object) -> tuple[bool, str]:
    """Map HTTPError to validator result."""
    expired_msg: str = "Session expired. Run: idle lc login"
    challenge_msg: str = "LeetCode challenge detected (captcha/cloudflare). Retry later."
    body: str = ""
    try:
        read = getattr(exc, "read", None)
        if callable(read):
            raw = read()
            if isinstance(raw, bytes):
                body = str(raw.decode("utf-8", "replace")[:8192])
    except (OSError, ValueError):
        body = ""
    code: int = int(getattr(exc, "code", 0) or 0)
    if code in (401, 403) or is_expired(code, body):
        return (False, expired_msg)
    if is_challenge(body):
        return (False, challenge_msg)
    return (False, f"login failed: HTTP {code} from LeetCode (retry later).")


def _explain_ok_body(code: int, raw: str) -> tuple[bool, str]:
    """Map 200 body to validator result."""
    expired_msg: str = "Session expired. Run: idle lc login"
    challenge_msg: str = "LeetCode challenge detected (captcha/cloudflare). Retry later."
    if is_expired(code, raw):
        return (False, expired_msg)
    if is_challenge(raw):
        return (False, challenge_msg)
    try:
        payload: object = json.loads(raw)
    except ValueError:
        return (False, expired_msg)
    if _is_valid_session_payload(payload):
        return (True, "")
    return (False, expired_msg)


def validate_session_cookies(
    cookies: dict[str, str], timeout: int = 10
) -> tuple[bool, str]:
    """Validate session cookies with one lightweight check.

    >>> callable(validate_session_cookies)
    True
    """
    import urllib.error
    import urllib.request

    offline_msg: str = "could not login (offline?). Check network and retry."
    query: str = "query userStatus { userStatus { username isSignedIn } }"
    data: bytes = json.dumps(
        {"query": query, "variables": {}, "operationName": "userStatus"}
    ).encode("utf-8")
    req = urllib.request.Request(
        "https://leetcode.com/graphql",
        data=data,
        headers=_validator_headers(cookies),
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw: str = resp.read().decode("utf-8", "replace")
            code: int = int(getattr(resp, "status", 200) or 200)
    except urllib.error.HTTPError as exc:
        return _explain_http_error(exc)
    except OSError:
        return (False, offline_msg)
    return _explain_ok_body(code, raw)
