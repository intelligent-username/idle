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


def test_cli_typing_and_leetcode_aliases() -> None:
    from idle.cli import build_parser

    parser = build_parser()
    args1 = parser.parse_args(["typing"])
    assert args1.command == "typing"
    args2 = parser.parse_args(["leetcode", "list"])
    assert args2.command == "leetcode"
    assert args2.lc_command == "list"


def test_cli_gui_flag_on_subcommands() -> None:
    from idle.cli import build_parser

    parser = build_parser()
    args1 = parser.parse_args(["type", "--gui"])
    assert args1.command == "type"
    assert args1.gui is True

    args2 = parser.parse_args(["drill", "--gui"])
    assert args2.command == "drill"
    assert args2.gui is True

    args3 = parser.parse_args(["lc", "--gui"])
    assert args3.command == "lc"
    assert args3.gui is True

    args4 = parser.parse_args(["--gui", "stats"])
    assert args4.command == "stats"
    assert args4.gui is True
