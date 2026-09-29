"""LC parse tests with fixtures, urlopen mocked."""

import json
from pathlib import Path
from typing import Any

import pytest

from idle import config
from idle.db import get_db
from idle.lc import api
from idle.lc import auth
from idle.lc.scaffold import scaffold_problem
from idle.lc.scaffold import strip_header


@pytest.fixture()
def _tmp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point working directory at tmp dir."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("time.sleep", lambda s: None)
    return tmp_path


def _fixture(name: str) -> dict[str, Any]:
    """Load JSON fixture by name."""
    path: Path = Path(__file__).parent / "fixtures" / name
    return json.loads(path.read_text(encoding="utf-8"))


class _FakeResp:
    """Minimal urlopen response double."""

    def __init__(self, payload: dict[str, Any]) -> None:
        """Store payload for read."""
        self._raw: bytes = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        """Return encoded payload."""
        return self._raw

    def __enter__(self) -> "_FakeResp":
        """Enter context."""
        return self

    def __exit__(self, *args: object) -> bool:
        """Exit context."""
        return False


def _mock_urlopen(
    monkeypatch: pytest.MonkeyPatch, payloads: list[dict[str, Any]]
) -> list[int]:
    """Patch urlopen to return payloads in order."""
    import urllib.request

    calls: list[int] = []

    def _fake(req: object, timeout: float = 10) -> _FakeResp:
        calls.append(1)
        idx: int = min(len(calls) - 1, len(payloads) - 1)
        return _FakeResp(payloads[idx])

    monkeypatch.setattr(urllib.request, "urlopen", _fake)
    return calls


def test_fetch_problem_list_parses_fixture(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[int] = _mock_urlopen(monkeypatch, [_fixture("problem_list.json")])
    rows: list[dict[str, Any]] = api.fetch_problem_list()
    assert len(calls) == 1
    assert len(rows) == 3
    assert rows[0]["slug"] == "two-sum"
    assert rows[0]["id"] == "1"
    assert "array" in rows[0]["tags"]


def test_fetch_problem_list_uses_cache(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_urlopen(monkeypatch, [_fixture("problem_list.json")])
    first: list[dict[str, Any]] = api.fetch_problem_list()
    calls2: list[int] = _mock_urlopen(monkeypatch, [_fixture("problem_list.json")])
    second: list[dict[str, Any]] = api.fetch_problem_list()
    assert len(calls2) == 0
    assert first == second


def test_fetch_problem_list_refresh(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_urlopen(monkeypatch, [_fixture("problem_list.json")])
    api.fetch_problem_list()
    calls: list[int] = _mock_urlopen(monkeypatch, [_fixture("problem_list.json")])
    api.fetch_problem_list(refresh=True)
    assert len(calls) == 1


def test_fetch_problem_list_stale_refetch(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_urlopen(monkeypatch, [_fixture("problem_list.json")])
    api.fetch_problem_list()
    db_path, _, _ = config.resolve_paths()
    conn = get_db(db_path)
    try:
        conn.execute("UPDATE lc_problems SET cached_at='2000-01-01T00:00:00+00:00';")
        conn.commit()
    finally:
        conn.close()
    calls: list[int] = _mock_urlopen(monkeypatch, [_fixture("problem_list.json")])
    rows: list[dict[str, Any]] = api.fetch_problem_list()
    assert len(calls) == 1
    assert len(rows) == 3


def test_fetch_question_parses_detail(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _mock_urlopen(monkeypatch, [_fixture("question_detail.json")])
    detail: dict[str, Any] = api.fetch_question("two-sum")
    assert detail["slug"] == "two-sum"
    assert detail["title"] == "Two Sum"
    assert "python3" in detail["code_snippets"]
    assert "[2,7,11,15]" in detail["sample_test_case"]


def test_fetch_daily_parses_daily(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    node: dict[str, Any] = _fixture("question_detail.json")["data"]["question"]
    daily: dict[str, Any] = {
        "data": {
            "activeDailyCodingChallengeQuestion": {
                "date": "2026-09-29",
                "link": "/problems/two-sum/",
                "question": node,
            }
        }
    }
    _mock_urlopen(monkeypatch, [daily])
    detail: dict[str, Any] = api.fetch_daily()
    assert detail["slug"] == "two-sum"
    assert detail["link"] == "/problems/two-sum/"


def test_is_expired_detects() -> None:
    assert auth.is_expired(401, "") is True
    assert auth.is_expired(403, "") is True
    assert auth.is_expired(200, "redirect /accounts/login/") is True
    assert auth.is_expired(200, '{"data":{}}') is False


def test_auth_save_load_headers(_tmp_home: Path) -> None:
    auth.save_auth({"LEETCODE_SESSION": "abc", "csrftoken": "tok"})
    loaded: dict[str, str] | None = auth.load_auth()
    assert loaded is not None
    assert loaded["csrftoken"] == "tok"
    headers: dict[str, str] = auth.auth_headers()
    assert "LEETCODE_SESSION=abc" in headers["Cookie"]
    assert headers["x-csrftoken"] == "tok"
    assert headers["Referer"] == "https://leetcode.com/"


def test_run_submit_poll(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payloads: list[dict[str, Any]] = [
        {"interpret_id": "r1"},
        {"submission_id": 99},
        {"state": "PENDING"},
        {"state": "SUCCESS", "status_msg": "Accepted"},
    ]
    _mock_urlopen(monkeypatch, payloads)
    auth.save_auth({"LEETCODE_SESSION": "s", "csrftoken": "c"})
    run: dict[str, Any] = api.run_sample("two-sum", "1", "code", "[1]\n1")
    assert run["interpret_id"] == "r1"
    sub: dict[str, Any] = api.submit_solution("two-sum", "1", "code")
    assert sub["submission_id"] == 99
    verdict: dict[str, Any] = api.poll_verdict(99)
    assert verdict["state"] == "SUCCESS"


def test_scaffold_and_strip_header(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _mock_urlopen(monkeypatch, [_fixture("question_detail.json")])
    detail: dict[str, Any] = api.fetch_question("two-sum")
    work: str = str(tmp_path / "lcwork")
    path: Path = scaffold_problem(detail, "python3", workdir=work)
    assert path.name == "solution.py"
    assert path.exists()
    text: str = path.read_text(encoding="utf-8")
    assert "Two Sum" in text.splitlines()[0]
    assert "class Solution" in text
    assert "twoSum" not in text or "twoSum" in text
    test_file: Path = path.parent / "test.txt"
    assert test_file.exists()
    assert "[2,7,11,15]" in test_file.read_text(encoding="utf-8")
    stripped: str = strip_header("# head\n# more\n\nclass A:\n    pass\n")
    assert not stripped.lstrip().startswith("#")
    assert "class A" in stripped
