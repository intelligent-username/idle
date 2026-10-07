"""Tests for Codewars parsing, auth, scaffolding, and rendering."""

import os
from pathlib import Path
from unittest.mock import patch

from idle.cw import api as cw_api
from idle.cw import auth as cw_auth
from idle.cw import render as cw_render
from idle.cw import scaffold as cw_scaffold


def test_env_reading(monkeypatch) -> None:
    monkeypatch.setenv("CODEWARS_API_KEY", "test_key_12345")
    monkeypatch.setenv("CODEWARS_USERNAME", "test_user")
    key, user = cw_auth.get_env_credentials()
    assert key == "test_key_12345"
    assert user == "test_user"


def test_auth_headers(monkeypatch) -> None:
    monkeypatch.setenv("CODEWARS_API_KEY", "secret_token")
    headers = cw_auth.auth_headers()
    assert headers.get("Authorization") == "secret_token"
    assert "User-Agent" in headers


def test_curated_catalog() -> None:
    katas = cw_api.CURATED_KATAS
    assert len(katas) >= 10
    for k in katas:
        assert "id" in k
        assert "slug" in k
        assert "name" in k
        assert "rank" in k
        assert "name" in k["rank"]


def test_kata_markdown_render() -> None:
    raw_md = "# Kata Title\n\nThis is [a link](https://example.com).\n\n```python\ndef solve(): pass\n```"
    rendered = cw_render.clean_markdown(raw_md)
    assert "=== Kata Title ===" in rendered
    assert "a link (https://example.com)" in rendered
    assert "def solve(): pass" in rendered


def test_kata_detail_format() -> None:
    sample_kata = {
        "name": "Even or Odd",
        "slug": "even-or-odd",
        "rank": {"name": "8 kyu"},
        "tags": ["Fundamentals", "Math"],
        "createdBy": {"username": "author1"},
        "description": "Create a function that takes an integer.",
    }
    formatted = cw_render.format_kata_detail(sample_kata)
    assert "KATA: Even or Odd [8 kyu]" in formatted
    assert "author1" in formatted
    assert "Create a function that takes an integer." in formatted


def test_strip_header() -> None:
    code = "# Codewars: Title\n# URL: https://example.com\n\ndef solution():\n    return 42\n"
    stripped = cw_scaffold.strip_header(code)
    assert stripped.startswith("def solution():")
    assert "return 42" in stripped


def test_scaffold_kata(tmp_path: Path) -> None:
    sample = {
        "name": "Multiply Numbers",
        "slug": "multiply-numbers",
        "rank": {"name": "8 kyu"},
        "url": "https://www.codewars.com/kata/multiply-numbers",
    }
    file_path = cw_scaffold.scaffold_kata(sample, workdir=str(tmp_path))
    assert file_path.exists()
    assert file_path.name == "cw_multiply_numbers.py"
    content = file_path.read_text(encoding="utf-8")
    assert "Multiply Numbers" in content
    assert "def solution(*args, **kwargs):" in content
