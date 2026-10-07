"""Codewars authentication and credential storage."""

import json
import os
from pathlib import Path
from typing import Any
import urllib.error
import urllib.request

USER_AGENT: str = "idle-cli/0.1.0 (python)"


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
    """Return (api_key, username) from environment or .env file."""
    env: dict[str, str] = load_dotenv()
    api_key: str = (
        os.environ.get("CODEWARS_API_KEY")
        or os.environ.get("CW_API_KEY")
        or os.environ.get("CODEWARS_KEY")
        or env.get("CODEWARS_API_KEY")
        or env.get("CW_API_KEY")
        or env.get("CODEWARS_KEY")
        or ""
    )
    username: str = (
        os.environ.get("CODEWARS_USERNAME")
        or os.environ.get("CW_USERNAME")
        or env.get("CODEWARS_USERNAME")
        or env.get("CW_USERNAME")
        or ""
    )
    return (api_key.strip(), username.strip())


def _auth_path() -> Path:
    """Return auth file path, ensuring parent dirs."""
    from idle.config import resolve_paths

    _, _, auth_path = resolve_paths()
    return auth_path


def load_saved_credentials() -> tuple[str, str]:
    """Return (api_key, username) from auth.json if saved, else .env."""
    path: Path = _auth_path()
    if path.exists():
        try:
            raw: str = path.read_text(encoding="utf-8")
            data: Any = json.loads(raw)
            if isinstance(data, dict):
                k: str = str(
                    data.get("codewars_api_key")
                    or data.get("cw_api_key")
                    or data.get("api_key", "")
                ).strip()
                u: str = str(
                    data.get("codewars_username")
                    or data.get("cw_username")
                    or data.get("username", "")
                ).strip()
                if k or u:
                    return (k, u)
        except (OSError, ValueError):
            pass
    return get_env_credentials()


def save_auth(api_key: str, username: str = "") -> None:
    """Save Codewars API key and username to auth file with 0600 permissions."""
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
    if api_key:
        payload["codewars_api_key"] = api_key
    if username:
        payload["codewars_username"] = username
    data: str = json.dumps(payload, indent=2)
    path.write_text(data, encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_auth() -> dict[str, str] | None:
    """Load saved Codewars auth dictionary, return None when missing."""
    key, user = load_saved_credentials()
    if key or user:
        return {"api_key": key, "username": user}
    return None


def auth_headers() -> dict[str, str]:
    """Build Authorization and User-Agent headers."""
    headers: dict[str, str] = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    key, _ = load_saved_credentials()
    if key:
        headers["Authorization"] = key
    return headers


def validate_credentials(api_key: str = "", username: str = "") -> tuple[bool, str]:
    """Validate Codewars username and/or API key against the public API."""
    if not username and not api_key:
        return False, "Provide at least a Codewars username or API key."

    test_user: str = username or "xDranik"
    url: str = f"https://www.codewars.com/api/v1/users/{test_user}"
    headers: dict[str, str] = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }
    if api_key:
        headers["Authorization"] = api_key

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
            retrieved_user = data.get("username", "")
            return True, f"Authenticated successfully as {retrieved_user}"
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return False, f"Codewars user '{username}' not found."
        if exc.code == 401 or exc.code == 403:
            return False, "Invalid Codewars API key."
        return False, f"Codewars API returned HTTP {exc.code}."
    except (urllib.error.URLError, OSError):
        return False, "Could not reach Codewars API (offline?)."
