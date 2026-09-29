"""Config tests using tmp_path only."""

import os
from pathlib import Path

import pytest

from idle import config


@pytest.fixture()
def _tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home: Path = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "appdata"))
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home


def test_resolve_paths_uses_tmp(_tmp_home: Path) -> None:
    db_path, cfg_path, auth_path = config.resolve_paths()
    assert str(db_path).startswith(os.environ["XDG_DATA_HOME"] if os.name != "nt" else os.environ["APPDATA"])
    assert cfg_path.parent.exists()
    assert db_path.parent.exists()


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
