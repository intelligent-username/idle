"""Config tests using tmp_path only."""

import os
from pathlib import Path

import pytest

from idle import config


@pytest.fixture()
def _tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_resolve_paths_uses_tmp(_tmp_home: Path) -> None:
    db_path, cfg_path, auth_path = config.resolve_paths()
    assert db_path == _tmp_home / "idle.db"
    assert cfg_path == _tmp_home / "config.toml"
    assert auth_path == _tmp_home / "auth.json"


def test_load_config_autocreates_defaults(_tmp_home: Path) -> None:
    cfg = config.load_config()
    assert cfg["typing"]["default_time"] == 60
    assert cfg["typing"]["word_list"] == 200
    assert cfg["lc"]["language"] == "python3"
    _, cfg_path, _ = config.resolve_paths()
    assert cfg_path.exists()


def test_load_config_merges_missing_keys(_tmp_home: Path) -> None:
    config.save_default_config()
    _, cfg_path, _ = config.resolve_paths()
    text: str = cfg_path.read_text(encoding="utf-8")
    text = text.replace("default_time = 60", "")
    cfg_path.write_text(text, encoding="utf-8")
    cfg = config.load_config()
    assert cfg["typing"]["default_time"] == 60


def test_save_default_config_idempotent(_tmp_home: Path) -> None:
    config.save_default_config()
    _, cfg_path, _ = config.resolve_paths()
    first: str = cfg_path.read_text(encoding="utf-8")
    config.save_default_config()
    second: str = cfg_path.read_text(encoding="utf-8")
    assert first == second
