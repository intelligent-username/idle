"""Path, config, and auth file resolution."""

import os
import tomllib
from pathlib import Path
from typing import Any

DEFAULT_CONFIG: dict[str, dict[str, Any]] = {
    "typing": {
        "default_mode": "time",
        "default_time": 60,
        "default_words": 50,
        "word_list": 200,
        "stop_on_error": False,
        "punct": False,
        "numbers": False,
    },
    "lc": {
        "language": "python3",
        "workdir": "~/leetcode",
        "editor": "",
    },
}


def _home() -> Path:
    return Path.home()


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _ensure_auth_perms(auth_path: Path) -> None:
    if not auth_path.exists():
        return
    try:
        os.chmod(auth_path, 0o600)
    except OSError:
        pass
    # Note: on Windows os.chmod is best effort, ACLs need icacls.


def _emit_toml(config: dict[str, dict[str, Any]]) -> str:
    lines: list[str] = []
    for section in ("typing", "lc"):
        lines.append(f"[{section}]")
        values: dict[str, Any] = config.get(section, {})
        for key, value in values.items():
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    return "\n".join(lines)


def _toml_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{value}"'


def _merge_defaults(loaded: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for section, defaults in DEFAULT_CONFIG.items():
        base: dict[str, Any] = dict(defaults)
        override: Any = loaded.get(section, {})
        if isinstance(override, dict):
            for key, value in override.items():
                if key in base:
                    base[key] = value
        merged[section] = base
    return merged


def resolve_paths() -> tuple[Path, Path, Path]:
    """Return (db_path, config_path, auth_path) in the local working directory."""
    base: Path = Path.cwd()
    db_path: Path = base / "idle.db"
    config_path: Path = base / "config.toml"
    auth_path: Path = base / "auth.json"
    _ensure_parent(db_path)
    _ensure_parent(config_path)
    _ensure_parent(auth_path)
    _ensure_auth_perms(auth_path)
    return (db_path, config_path, auth_path)


def save_default_config() -> None:
    """Write default config file, creating parent dirs."""
    _, config_path, _ = resolve_paths()
    _ensure_parent(config_path)
    config_path.write_text(_emit_toml(DEFAULT_CONFIG), encoding="utf-8")


def load_config() -> dict[str, Any]:
    """Load config, auto-creating defaults and merging missing keys."""
    _, config_path, _ = resolve_paths()
    if not config_path.exists():
        save_default_config()
    raw: bytes = config_path.read_bytes()
    loaded: dict[str, Any] = tomllib.loads(raw.decode("utf-8"))
    return _merge_defaults(loaded)
