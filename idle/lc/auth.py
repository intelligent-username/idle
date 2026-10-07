"""LeetCode authentication helper functions."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

from idle import config


def is_expired(status_code: int, text: str) -> bool:
    """Check if response indicates expired auth."""
    if status_code in (401, 403):
        return True
    text_lower = text.lower()
    expired_markers = [
        "redirect /accounts/login/",
        "unauthorized access",
        "session expired, login again",
        "csrf verification failed",
        "invalid session token",
    ]
    return any(marker in text_lower for marker in expired_markers)


def is_challenge(text: str) -> bool:
    """Check if response is a Cloudflare / captcha challenge page."""
    text_lower = text.lower()
    challenge_markers = ["cf_clearance", "cloudflare", "captcha", "verify you are human"]
    return any(marker in text_lower for marker in challenge_markers)


def save_auth(data: dict[str, str], username: str | None = None, password: str | None = None) -> None:
    """Save auth cookies and optional credentials to auth.json."""
    _, _, auth_path = config.resolve_paths()
    payload: dict[str, Any] = dict(data)
    if username is not None:
        payload["LC_USERNAME"] = username
    if password is not None:
        payload["LC_PW"] = password
    auth_path.write_text(json.dumps(payload), encoding="utf-8")


def load_auth() -> dict[str, str] | None:
    """Load auth cookies from auth.json if present."""
    _, _, auth_path = config.resolve_paths()
    if not auth_path.exists():
        return None
    try:
        data = json.loads(auth_path.read_text(encoding="utf-8"))
        cookies = {k: v for k, v in data.items() if k in ("LEETCODE_SESSION", "csrftoken")}
        return cookies if cookies else None
    except Exception:
        return None


def load_saved_credentials() -> tuple[str, str]:
    """Load saved LC_USERNAME and LC_PW from auth.json or .env."""
    _, _, auth_path = config.resolve_paths()
    if auth_path.exists():
        try:
            data = json.loads(auth_path.read_text(encoding="utf-8"))
            u = data.get("LC_USERNAME", "")
            p = data.get("LC_PW", "")
            if u or p:
                return u, p
        except Exception:
            pass

    env_path = Path.cwd() / ".env"
    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        user, pw = "", ""
        for line in content.splitlines():
            if line.startswith("LC_USERNAME="):
                user = line.split("=", 1)[1].strip()
            elif line.startswith("LC_PW="):
                pw = line.split("=", 1)[1].strip()
        return user, pw

    return os.getenv("LC_USERNAME", ""), os.getenv("LC_PW", "")


def auth_headers() -> dict[str, str]:
    """Build request headers for LeetCode API requests."""
    headers: dict[str, str] = {
        "Referer": "https://leetcode.com/",
        "Origin": "https://leetcode.com",
        "X-Requested-With": "XMLHttpRequest",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    }
    cookies = load_auth()
    if cookies:
        headers["Cookie"] = f"LEETCODE_SESSION={cookies.get('LEETCODE_SESSION', '')}; csrftoken={cookies.get('csrftoken', '')}"
        if "csrftoken" in cookies:
            headers["x-csrftoken"] = cookies["csrftoken"]
    return headers


def login_username_password(username: str, password: str) -> dict[str, str]:
    """Attempt username/password login."""
    if not username or not password:
        raise RuntimeError("login failed: empty username or password")

    try:
        import http.cookiejar

        cj = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

        req_login_page = urllib.request.Request("https://leetcode.com/accounts/login/")
        resp = opener.open(req_login_page)
        html_text = resp.read().decode("utf-8") if hasattr(resp, "read") else str(resp)

        if "csrfmiddlewaretoken" not in html_text:
            raise RuntimeError("login failed: could not find login token (page changed?)")

        cookies: dict[str, str] = {}
        for c in cj:
            cookies[c.name] = c.value

        return cookies
    except RuntimeError:
        raise
    except urllib.error.HTTPError as err:
        try:
            body = err.read().decode("utf-8", errors="ignore")
        except Exception:
            body = ""
        if is_challenge(body):
            raise RuntimeError("LeetCode challenge detected (captcha/cloudflare). Retry later.")
        raise RuntimeError(f"login failed: HTTP {err.code} from LeetCode (retry later).")
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("could not login (offline?). Check network and retry.")
    except Exception as err:
        raise RuntimeError(f"login failed: {err}")


def validate_session_cookies(cookies: dict[str, str]) -> tuple[bool, str]:
    """Validate cookies against LeetCode GraphQL."""
    from idle.lc.api import GRAPHQL_URL
    req = urllib.request.Request(GRAPHQL_URL)
    req.add_header("Cookie", f"LEETCODE_SESSION={cookies.get('LEETCODE_SESSION', '')}; csrftoken={cookies.get('csrftoken', '')}")
    req.add_header("x-csrftoken", cookies.get("csrftoken", ""))
    req.add_header("Referer", "https://leetcode.com/")
    req.add_header("Origin", "https://leetcode.com")
    req.add_header("X-Requested-With", "XMLHttpRequest")
    req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

    query = json.dumps({"query": "query { userStatus { username isSignedIn } }"}).encode("utf-8")
    req.add_header("Content-Type", "application/json")
    req.data = query

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("data", {}).get("userStatus", {}).get("isSignedIn"):
                return True, ""
            return False, "Session expired. Run: idle lc login"
    except urllib.error.HTTPError as err:
        if err.code in (401, 403):
            return False, "Session expired. Run: idle lc login"
        return False, f"login failed: HTTP {err.code}"
    except (urllib.error.URLError, TimeoutError):
        return False, "could not validate cookies (offline?). Check network and retry."
    except Exception as err:
        return False, str(err)
