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


def _mock_urlopen_capture(
    monkeypatch: pytest.MonkeyPatch, payloads: list[dict[str, Any]]
) -> tuple[list[int], list[Any]]:
    """Patch urlopen and capture Request objects in order."""
    import urllib.request

    calls: list[int] = []
    seen: list[Any] = []

    def _fake(req: object, timeout: float = 10) -> _FakeResp:
        calls.append(1)
        seen.append(req)
        idx: int = min(len(calls) - 1, len(payloads) - 1)
        return _FakeResp(payloads[idx])

    monkeypatch.setattr(urllib.request, "urlopen", _fake)
    return calls, seen


def _headers_lower(req: Any) -> dict[str, str]:
    """Return lowercased header mapping for a Request."""
    merged: dict[str, str] = {}
    for source in (
        getattr(req, "headers", {}),
        getattr(req, "unredirected_hdrs", {}),
    ):
        if isinstance(source, dict):
            for key, value in source.items():
                merged[str(key).lower()] = str(value)
    return merged


def _payload_of(req: Any) -> dict[str, Any]:
    """Decode JSON body of a captured Request."""
    data: Any = getattr(req, "data", None)
    if not data:
        return {}
    raw: bytes = bytes(data)
    return json.loads(raw.decode("utf-8"))


def _make_list_payload(total: int, start: int, count: int) -> dict[str, Any]:
    """Build a problem-list page payload for paging tests."""
    questions: list[dict[str, Any]] = []
    for idx in range(start, start + count):
        questions.append(
            {
                "acRate": 50.0,
                "difficulty": "Easy",
                "frontendQuestionId": str(idx + 1),
                "title": f"Problem {idx + 1}",
                "titleSlug": f"problem-{idx + 1}",
                "topicTags": [],
                "status": None,
            }
        )
    return {"data": {"problemsetQuestionList": {"total": total, "questions": questions}}}


class _FakeLoginResp:
    """Minimal opener response double for login flow."""

    def __init__(self, text: str) -> None:
        """Store text body."""
        self._raw: bytes = text.encode("utf-8")

    def read(self) -> bytes:
        """Return encoded body."""
        return self._raw

    def __enter__(self) -> "_FakeLoginResp":
        """Enter context."""
        return self

    def __exit__(self, *args: object) -> bool:
        """Exit context."""
        return False


class _FakeCookie:
    """Minimal cookie with name and value."""

    def __init__(self, name: str, value: str) -> None:
        """Store name and value."""
        self.name: str = name
        self.value: str = value


class _FakeOpener:
    """Opener double returning canned HTML pages."""

    def __init__(self, pages: list[str]) -> None:
        """Store pages to return in order."""
        self._pages: list[str] = pages
        self.calls: int = 0

    def open(self, req: object, timeout: float = 10) -> _FakeLoginResp:
        """Return next canned page."""
        idx: int = min(self.calls, len(self._pages) - 1)
        self.calls += 1
        return _FakeLoginResp(self._pages[idx])


class _StepOpener:
    """Opener returning pages or raising errors in order."""

    def __init__(self, steps: list[object]) -> None:
        """Store steps of text or exception."""
        self._steps: list[object] = steps
        self.calls: int = 0

    def open(self, req: object, timeout: float = 10) -> _FakeLoginResp:
        """Return next page or raise next error."""
        idx: int = min(self.calls, len(self._steps) - 1)
        self.calls += 1
        step: object = self._steps[idx]
        if isinstance(step, Exception):
            raise step
        return _FakeLoginResp(str(step))


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
    assert len(first) == len(second)
    assert [row["slug"] for row in first] == [row["slug"] for row in second]
    assert [row["id"] for row in first] == [row["id"] for row in second]


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
    daily: dict[str, Any] = {
        "data": {
            "activeDailyCodingChallengeQuestion": {
                "date": "2026-09-29",
                "link": "/problems/two-sum/",
                "question": {"titleSlug": "two-sum"},
            }
        }
    }
    calls, seen = _mock_urlopen_capture(
        monkeypatch, [daily, _fixture("question_detail.json")]
    )
    detail: dict[str, Any] = api.fetch_daily()
    assert len(calls) == 2
    first: dict[str, Any] = _payload_of(seen[0])
    assert "questionOfToday" in str(first.get("query", ""))
    assert "query daily()" not in str(first.get("query", ""))
    assert detail["slug"] == "two-sum"
    assert detail["link"] == "/problems/two-sum/"


def test_fetch_daily_missing_slug_raises(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty: dict[str, Any] = {
        "data": {"activeDailyCodingChallengeQuestion": {"date": "", "link": ""}}
    }
    _mock_urlopen(monkeypatch, [empty])
    with pytest.raises(RuntimeError, match="daily challenge not found"):
        api.fetch_daily()


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


def test_list_vars_essentials_operation_limit(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """LIST uses all-code-essentials, filters {}, operationName, limit<=100."""
    calls, seen = _mock_urlopen_capture(
        monkeypatch, [_fixture("problem_list.json")]
    )
    api.fetch_problem_list(refresh=True)
    assert len(calls) == 1
    payload: dict[str, Any] = _payload_of(seen[0])
    assert payload.get("operationName") == "problemsetQuestionList"
    variables: dict[str, Any] = payload.get("variables", {})
    assert variables.get("categorySlug") == "all-code-essentials"
    assert variables.get("filters") == {}
    assert isinstance(variables.get("limit"), int)
    assert int(variables["limit"]) <= 100
    assert isinstance(variables.get("skip"), int)


def test_list_paging_total_250_three_calls(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Total 250 with 100-row pages triggers exactly 3 urlopen calls."""
    payloads: list[dict[str, Any]] = [
        _make_list_payload(250, 0, 100),
        _make_list_payload(250, 100, 100),
        _make_list_payload(250, 200, 50),
    ]
    calls, _seen = _mock_urlopen_capture(monkeypatch, payloads)
    rows: list[dict[str, Any]] = api.fetch_problem_list(refresh=True)
    assert len(calls) == 3
    assert len(rows) == 250


def test_post_json_referer_origin(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_post_json sets problem Referer plus Origin and X-Requested-With."""
    payloads: list[dict[str, Any]] = [{"interpret_id": "r1"}]
    _calls, seen = _mock_urlopen_capture(monkeypatch, payloads)
    auth.save_auth({"LEETCODE_SESSION": "s", "csrftoken": "c"})
    api.run_sample("two-sum", "1", "code", "[1]")
    headers: dict[str, str] = _headers_lower(seen[0])
    assert headers.get("referer") == "https://leetcode.com/problems/two-sum/"
    assert headers.get("origin") == "https://leetcode.com"
    assert headers.get("x-requested-with") == "XMLHttpRequest"
    assert "mozilla" in headers.get("user-agent", "").lower()
    assert "idle-lc/0.1" not in headers.get("user-agent", "")


def test_tolerant_interpret_submission_ids(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """CamelCase interpretId/submissionId normalize without KeyError."""
    payloads: list[dict[str, Any]] = [
        {"interpretId": "camel-r1"},
        {"submissionId": 101},
    ]
    _mock_urlopen(monkeypatch, payloads)
    auth.save_auth({"LEETCODE_SESSION": "s", "csrftoken": "c"})
    run: dict[str, Any] = api.run_sample("two-sum", "1", "code", "[1]")
    assert run.get("interpret_id") == "camel-r1"
    assert run.get("interpretId") == "camel-r1"
    sub: dict[str, Any] = api.submit_solution("two-sum", "1", "code")
    assert sub.get("submission_id") == 101
    assert sub.get("submissionId") == 101


def test_is_expired_extended() -> None:
    """Extended markers detect expired sessions."""
    assert auth.is_expired(200, "unauthorized access") is True
    assert auth.is_expired(200, "session expired, login again") is True
    assert auth.is_expired(200, "csrf verification failed") is True
    assert auth.is_expired(200, "invalid session token") is True
    assert auth.is_expired(200, '{"data":{"question": {}}}') is False


def test_is_challenge_distinct() -> None:
    """Challenge pages differ from expired sessions."""
    body: str = "Just a moment... cf_clearance verify you are human"
    assert auth.is_challenge(body) is True
    assert auth.is_expired(200, body) is False
    assert auth.is_challenge('{"data":{}}') is False
    assert auth.is_challenge("cloudflare attention required captcha") is True


def test_auth_headers_public_and_browser_ua(_tmp_home: Path) -> None:
    """Public fetch has no Cookie yet keeps browser headers."""
    headers: dict[str, str] = auth.auth_headers()
    assert "Cookie" not in headers
    assert headers.get("Referer") == "https://leetcode.com/"
    assert headers.get("Origin") == "https://leetcode.com"
    assert headers.get("X-Requested-With") == "XMLHttpRequest"
    assert "mozilla" in headers.get("User-Agent", "").lower()
    assert headers.get("User-Agent") != "idle-lc/0.1"


def test_login_username_password_mocked(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mocked jar login returns cookies and round-trips via save."""
    import http.cookiejar
    import urllib.request

    cookies_in: list[_FakeCookie] = [
        _FakeCookie("LEETCODE_SESSION", "sess123"),
        _FakeCookie("csrftoken", "csrf123"),
    ]
    login_html: str = (
        '<input type="hidden" name="csrfmiddlewaretoken" value="tok123">'
    )
    monkeypatch.setattr(http.cookiejar, "CookieJar", lambda: cookies_in)
    monkeypatch.setattr(
        urllib.request, "build_opener", lambda *a: _FakeOpener([login_html, "ok"])
    )
    cookies: dict[str, str] = auth.login_username_password("user", "pass")
    assert cookies == {"LEETCODE_SESSION": "sess123", "csrftoken": "csrf123"}
    auth.save_auth(cookies)
    loaded: dict[str, str] | None = auth.load_auth()
    assert loaded == cookies


def test_login_empty_credentials_no_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty credentials raise gracefully without touching network."""
    calls: list[int] = _mock_urlopen(monkeypatch, [{}])
    with pytest.raises(RuntimeError, match="login failed"):
        auth.login_username_password("", "")
    assert len(calls) == 0


def test_login_fetch_challenge_not_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 403 with challenge body maps to challenge."""
    import http.cookiejar
    import io
    import urllib.error
    import urllib.request
    from email.message import Message

    body: bytes = b"<html>captcha verify you are human</html>"
    exc = urllib.error.HTTPError(
        "https://leetcode.com/accounts/login/",
        403,
        "Forbidden",
        Message(),
        io.BytesIO(body),
    )
    monkeypatch.setattr(http.cookiejar, "CookieJar", lambda: [])
    monkeypatch.setattr(
        urllib.request, "build_opener", lambda *a: _StepOpener([exc])
    )
    with pytest.raises(RuntimeError) as err:
        auth.login_username_password("user", "pass")
    text: str = str(err.value).lower()
    assert "challenge" in text
    assert "offline" not in text


def test_login_fetch_http_403_without_challenge(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTP 403 without challenge maps to HTTP error."""
    import http.cookiejar
    import io
    import urllib.error
    import urllib.request
    from email.message import Message

    body: bytes = b"<html>forbidden</html>"
    exc = urllib.error.HTTPError(
        "https://leetcode.com/accounts/login/",
        403,
        "Forbidden",
        Message(),
        io.BytesIO(body),
    )
    monkeypatch.setattr(http.cookiejar, "CookieJar", lambda: [])
    monkeypatch.setattr(
        urllib.request, "build_opener", lambda *a: _StepOpener([exc])
    )
    with pytest.raises(RuntimeError) as err:
        auth.login_username_password("user", "pass")
    text: str = str(err.value)
    assert "login failed: HTTP 403" in text
    assert "offline" not in text.lower()


def test_login_fetch_urlerror_maps_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """URLError maps to offline string."""
    import http.cookiejar
    import urllib.error
    import urllib.request

    monkeypatch.setattr(http.cookiejar, "CookieJar", lambda: [])
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *a: _StepOpener([urllib.error.URLError("dns fail")]),
    )
    with pytest.raises(RuntimeError) as err:
        auth.login_username_password("user", "pass")
    assert "offline" in str(err.value).lower()


def test_login_fetch_timeout_maps_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Timeout maps to offline string."""
    import http.cookiejar
    import urllib.request

    monkeypatch.setattr(http.cookiejar, "CookieJar", lambda: [])
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *a: _StepOpener([TimeoutError("timed out")]),
    )
    with pytest.raises(RuntimeError) as err:
        auth.login_username_password("user", "pass")
    assert "offline" in str(err.value).lower()


def test_login_token_missing_page_changed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTML without token maps to page-changed message."""
    import http.cookiejar
    import urllib.request

    monkeypatch.setattr(http.cookiejar, "CookieJar", lambda: [])
    monkeypatch.setattr(
        urllib.request,
        "build_opener",
        lambda *a: _FakeOpener(["<html>no token here</html>"]),
    )
    with pytest.raises(RuntimeError) as err:
        auth.login_username_password("user", "pass")
    text: str = str(err.value)
    assert "could not find login token" in text
    assert "offline" not in text.lower()


def test_load_saved_credentials_from_env(_tmp_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Reading LC_USERNAME and LC_PW from .env file or environment."""
    env_file = _tmp_home / ".env"
    env_file.write_text("LC_USERNAME=TestUser\nLC_PW=TestPass420\n", encoding="utf-8")
    user, pw = auth.load_saved_credentials()
    assert user == "TestUser"
    assert pw == "TestPass420"


def test_save_and_load_auth_with_credentials(_tmp_home: Path) -> None:
    """Saving cookies along with username and password round-trips via load_saved_credentials."""
    cookies = {"LEETCODE_SESSION": "sess-xyz", "csrftoken": "csrf-abc"}
    auth.save_auth(cookies, username="Alice", password="SecretPassword")
    assert auth.load_auth() == cookies
    user, pw = auth.load_saved_credentials()
    assert user == "Alice"
    assert pw == "SecretPassword"


def test_run_local_zero_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """run_local executes Solution without any urlopen call."""
    calls: list[int] = _mock_urlopen(monkeypatch, [{}])
    code: str = "class Solution:\n    def double(self, x: int) -> int:\n        return x * 2\n"
    result: dict[str, Any] = api.run_local(code, "2", "4")
    assert len(calls) == 0
    assert result.get("status_msg") == "Accepted"
    assert result.get("state") == "SUCCESS"


def test_run_local_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Broken code returns Runtime Error dict without raising."""
    calls: list[int] = _mock_urlopen(monkeypatch, [{}])
    bad: str = "class Solution:\n    def solve(self, x: int) -> int:\n        raise ValueError('boom')\n"
    result: dict[str, Any] = api.run_local(bad, "1", "1")
    assert len(calls) == 0
    assert result.get("status_msg") == "Runtime Error"
    assert str(result.get("error", "")) != ""


def test_poll_verdict_int_and_timeout(
    _tmp_home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """poll_verdict accepts int id and returns PENDING on timeout."""
    auth.save_auth({"LEETCODE_SESSION": "s", "csrftoken": "c"})
    pending: dict[str, Any] = {"state": "PENDING"}
    _mock_urlopen(monkeypatch, [pending])
    result: dict[str, Any] = api.poll_verdict(123)
    assert result.get("state") == "PENDING"


def test_no_leetcode_cli_fallback() -> None:
    """Guard keeps deleted CLI fallback from returning."""
    import importlib.util

    assert importlib.util.find_spec("idle.lc.api") is not None
    from idle.lc import api as lc_api

    assert hasattr(lc_api, "leetcode_cli_fallback") is False
    with pytest.raises(ImportError):
        from idle.lc.api import leetcode_cli_fallback  # type: ignore[attr-defined] # noqa: F401


def test_validate_session_cookies_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validator returns True on signed-in payload."""
    payload: dict[str, Any] = {
        "data": {"userStatus": {"username": "dummy", "isSignedIn": True}}
    }
    _mock_urlopen(monkeypatch, [payload])
    ok, msg = auth.validate_session_cookies(
        {"LEETCODE_SESSION": "sess123", "csrftoken": "csrf123"}
    )
    assert (ok, msg) == (True, "")


def test_validate_session_cookies_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """HTTPError 403 maps to expired message."""
    import io
    import urllib.error
    import urllib.request
    from email.message import Message

    def _fake(req: object, timeout: float = 10) -> _FakeResp:
        raise urllib.error.HTTPError(
            "https://leetcode.com/graphql",
            403,
            "Forbidden",
            Message(),
            io.BytesIO(b"forbidden"),
        )

    monkeypatch.setattr(urllib.request, "urlopen", _fake)
    ok, msg = auth.validate_session_cookies(
        {"LEETCODE_SESSION": "sess123", "csrftoken": "csrf123"}
    )
    assert ok is False
    assert msg == "Session expired. Run: idle lc login"


def test_validate_session_cookies_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """URLError maps to offline string."""
    import urllib.error
    import urllib.request

    def _fake(req: object, timeout: float = 10) -> _FakeResp:
        raise urllib.error.URLError("dns fail")

    monkeypatch.setattr(urllib.request, "urlopen", _fake)
    ok, msg = auth.validate_session_cookies(
        {"LEETCODE_SESSION": "sess123", "csrftoken": "csrf123"}
    )
    assert ok is False
    assert "offline" in msg.lower()
