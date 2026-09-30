"""GraphQL and REST client for LeetCode."""

import json
from typing import Any

TIMEOUT = 10
GRAPHQL_URL = "https://leetcode.com/graphql"
CACHE_TTL_DAYS = 7
_MAX_RETRIES = 2
_BACKOFF_S = (1.0, 2.0)

LIST_QUERY = """
query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
  problemsetQuestionList: questionList(categorySlug: $categorySlug, limit: $limit, skip: $skip, filters: $filters) {
    total: totalNum
    questions: data {
      acRate
      difficulty
      frontendQuestionId: questionFrontendId
      title
      titleSlug
      topicTags { name slug }
      status
    }
  }
}
"""

QUESTION_QUERY = """
query questionData($titleSlug: String!) {
  question(titleSlug: $titleSlug) {
    questionId
    questionFrontendId
    title
    titleSlug
    content
    difficulty
    acRate
    sampleTestCase
    exampleTestcases
    codeSnippets { lang langSlug code }
    topicTags { name slug }
  }
}
"""

DAILY_QUERY = """
query daily() {
  activeDailyCodingChallengeQuestion {
    date
    link
    question {
      questionId
      questionFrontendId
      title
      titleSlug
      content
      difficulty
      acRate
      sampleTestCase
      exampleTestcases
      codeSnippets { lang langSlug code }
      topicTags { name slug }
    }
  }
}
"""


class AuthExpiredError(RuntimeError):
    """Raised when LeetCode session needs relogin."""


def _headers(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Build request headers with auth cookies."""
    from idle.lc.auth import auth_headers

    base: dict[str, str] = auth_headers()
    base["Content-Type"] = "application/json"
    if extra:
        base.update(extra)
    return base


def _graphql_once(payload: bytes, headers: dict[str, str]) -> dict[str, Any]:
    """Send one GraphQL POST and return parsed JSON."""
    import urllib.request

    req = urllib.request.Request(
        GRAPHQL_URL, data=payload, headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        raw: bytes = resp.read()
    return json.loads(raw.decode("utf-8"))


def graphql(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    """POST GraphQL with timeout and retry on network errors."""
    import time
    import urllib.error

    from idle.lc.auth import is_expired

    payload: bytes = json.dumps(
        {"query": query, "variables": variables}
    ).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return _graphql_once(payload, _headers())
        except urllib.error.HTTPError as exc:
            body: str = ""
            try:
                body = exc.read().decode("utf-8", "replace")
            except Exception:
                body = ""
            if is_expired(exc.code, body):
                raise AuthExpiredError(
                    "Session expired. Run: idle lc login"
                ) from exc
            last_err = exc
            if attempt >= _MAX_RETRIES:
                break
            time.sleep(_BACKOFF_S[min(attempt, len(_BACKOFF_S) - 1)])
        except OSError as exc:
            last_err = exc
            if attempt >= _MAX_RETRIES:
                break
            time.sleep(_BACKOFF_S[min(attempt, len(_BACKOFF_S) - 1)])
    raise RuntimeError(f"graphql request failed: {last_err}")


def _parse_problem_list(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract problem rows from list payload."""
    data: Any = payload.get("data", {})
    if not isinstance(data, dict):
        return []
    node: Any = data.get("problemsetQuestionList") or data.get("questionList")
    if not isinstance(node, dict):
        return []
    raw_list: Any = node.get("questions") or node.get("data") or []
    out: list[dict[str, Any]] = []
    for item in raw_list if isinstance(raw_list, list) else []:
        if not isinstance(item, dict):
            continue
        out.append(_normalize_list_item(item))
    return out


def _normalize_list_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize one list entry to stable keys."""
    fid: str = str(
        item.get("frontendQuestionId") or item.get("questionFrontendId") or ""
    )
    tags: list[str] = []
    raw_tags: Any = item.get("topicTags") or []
    if isinstance(raw_tags, list):
        for tag in raw_tags:
            if isinstance(tag, dict) and tag.get("slug"):
                tags.append(str(tag["slug"]))
    return {
        "id": fid,
        "slug": str(item.get("titleSlug") or ""),
        "title": str(item.get("title") or ""),
        "difficulty": str(item.get("difficulty") or ""),
        "ac_rate": item.get("acRate"),
        "tags": tags,
        "status": item.get("status"),
    }


def _is_cache_fresh(cached_at: str) -> bool:
    """Check if cached_at is within TTL window."""
    from datetime import datetime
    from datetime import timezone

    try:
        ts = datetime.fromisoformat(cached_at)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - ts
        return delta.days < CACHE_TTL_DAYS
    except ValueError:
        return False


def _load_cached_problems(conn: Any) -> list[dict[str, Any]] | None:
    """Return cached rows when fresh, else None."""
    rows = conn.execute(
        "SELECT id, slug, title, difficulty, tags_json, cached_at"
        " FROM lc_problems ORDER BY id;"
    ).fetchall()
    if not rows:
        return None
    out: list[dict[str, Any]] = []
    for row in rows:
        if not _is_cache_fresh(str(row[5])):
            return None
        raw_tags: Any = json.loads(str(row[4])) if row[4] else []
        tags: list[Any] = raw_tags if isinstance(raw_tags, list) else []
        out.append(
            {
                "id": str(row[0]),
                "slug": str(row[1]),
                "title": str(row[2]),
                "difficulty": str(row[3]),
                "tags": tags,
            }
        )
    return out


def _build_problem_rows(
    problems: list[dict[str, Any]], now: str
) -> list[tuple[int, str, str, str, str, str]]:
    """Build upsert tuples skipping bad ids."""
    rows: list[tuple[int, str, str, str, str, str]] = []
    for item in problems:
        tags_json: str = json.dumps(item.get("tags", []))
        try:
            pid: int = int(str(item.get("id", "0")))
        except ValueError:
            continue
        rows.append(
            (
                pid,
                str(item.get("slug", "")),
                str(item.get("title", "")),
                str(item.get("difficulty", "")),
                tags_json,
                now,
            )
        )
    return rows


def _save_problems(conn: Any, problems: list[dict[str, Any]]) -> None:
    """Upsert problem list rows with fresh timestamp."""
    from datetime import datetime
    from datetime import timezone

    now: str = datetime.now(timezone.utc).isoformat()
    rows = _build_problem_rows(problems, now)
    if not rows:
        return
    conn.executemany(
        "INSERT INTO lc_problems(id, slug, title, difficulty,"
        " tags_json, cached_at) VALUES(?,?,?,?,?,?)"
        " ON CONFLICT(slug) DO UPDATE SET"
        " id=excluded.id, title=excluded.title,"
        " difficulty=excluded.difficulty,"
        " tags_json=excluded.tags_json, cached_at=excluded.cached_at;",
        rows,
    )
    conn.commit()


def fetch_problem_list(refresh: bool = False) -> list[dict[str, Any]]:
    """Fetch list, using weekly SQLite cache unless refresh."""
    from idle.config import resolve_paths
    from idle.db import get_db

    db_path, _, _ = resolve_paths()
    conn = get_db(db_path)
    try:
        if not refresh:
            cached = _load_cached_problems(conn)
            if cached is not None:
                return cached
        payload = graphql(LIST_QUERY, {"categorySlug": "", "skip": 0, "limit": 3000})
        problems = _parse_problem_list(payload)
        _save_problems(conn, problems)
        return problems
    finally:
        conn.close()


def _normalize_question(node: dict[str, Any]) -> dict[str, Any]:
    """Normalize detail node to stable keys."""
    snippets: dict[str, str] = {}
    raw_snips: Any = node.get("codeSnippets") or []
    if isinstance(raw_snips, list):
        for entry in raw_snips:
            if not isinstance(entry, dict):
                continue
            key: str = str(entry.get("langSlug") or entry.get("lang") or "")
            if key:
                snippets[key] = str(entry.get("code") or "")
    tags: list[str] = []
    raw_tags: Any = node.get("topicTags") or []
    if isinstance(raw_tags, list):
        for tag in raw_tags:
            if isinstance(tag, dict) and tag.get("slug"):
                tags.append(str(tag["slug"]))
    examples: str = str(
        node.get("exampleTestcases") or node.get("sampleTestCase") or ""
    )
    return {
        "question_id": str(node.get("questionId") or ""),
        "id": str(node.get("questionFrontendId") or ""),
        "slug": str(node.get("titleSlug") or ""),
        "title": str(node.get("title") or ""),
        "difficulty": str(node.get("difficulty") or ""),
        "content_html": str(node.get("content") or ""),
        "code_snippets": snippets,
        "sample_test_case": str(node.get("sampleTestCase") or ""),
        "example_testcases": examples,
        "tags": tags,
        "ac_rate": node.get("acRate"),
    }


def fetch_question(slug: str) -> dict[str, Any]:
    """Fetch fresh detail for slug, never cached."""
    payload = graphql(QUESTION_QUERY, {"titleSlug": slug})
    data: Any = payload.get("data", {})
    node: Any = data.get("question") if isinstance(data, dict) else None
    if not isinstance(node, dict):
        raise RuntimeError(f"question not found: {slug}")
    return _normalize_question(node)


def fetch_daily() -> dict[str, Any]:
    """Fetch daily challenge question detail."""
    payload = graphql(DAILY_QUERY, {})
    data: Any = payload.get("data", {})
    wrap: Any = (
        data.get("activeDailyCodingChallengeQuestion")
        if isinstance(data, dict)
        else None
    )
    node: Any = wrap.get("question") if isinstance(wrap, dict) else None
    if not isinstance(node, dict):
        raise RuntimeError("daily challenge not found")
    detail = _normalize_question(node)
    link: str = str(wrap.get("link", "")) if isinstance(wrap, dict) else ""
    if link:
        detail["link"] = link
    return detail


def _post_json(url: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST JSON with auth headers and expiry check."""
    import urllib.error
    import urllib.request

    from idle.lc.auth import is_expired

    data: bytes = json.dumps(payload).encode("utf-8")
    headers = _headers({"Referer": url.rsplit("/problems/", 1)[0] + "/"})
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw: bytes = resp.read()
    except urllib.error.HTTPError as exc:
        body: str = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        if is_expired(exc.code, body):
            raise AuthExpiredError("Session expired. Run: idle lc login") from exc
        raise RuntimeError(f"request failed: {exc.code}") from exc
    return json.loads(raw.decode("utf-8"))


def _get_json(url: str) -> dict[str, Any]:
    """GET JSON with auth headers and expiry check."""
    import urllib.error
    import urllib.request

    from idle.lc.auth import is_expired

    req = urllib.request.Request(url, headers=_headers(), method="GET")
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw: bytes = resp.read()
    except urllib.error.HTTPError as exc:
        body: str = ""
        try:
            body = exc.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        if is_expired(exc.code, body):
            raise AuthExpiredError("Session expired. Run: idle lc login") from exc
        raise RuntimeError(f"request failed: {exc.code}") from exc
    return json.loads(raw.decode("utf-8"))


def run_sample(
    slug: str,
    question_id: str,
    code: str,
    data_input: str,
    lang: str = "python3",
) -> dict[str, Any]:
    """Run sample cases remotely via interpret_solution."""
    url: str = f"https://leetcode.com/problems/{slug}/interpret_solution/"
    payload: dict[str, Any] = {
        "lang": lang,
        "question_id": question_id,
        "typed_code": code,
        "data_input": data_input,
    }
    return _post_json(url, payload)


def submit_solution(
    slug: str, question_id: str, code: str, lang: str = "python3"
) -> dict[str, Any]:
    """Submit solution remotely, return submission id."""
    url: str = f"https://leetcode.com/problems/{slug}/submit/"
    payload: dict[str, Any] = {
        "lang": lang,
        "question_id": question_id,
        "typed_code": code,
    }
    return _post_json(url, payload)


def poll_verdict(submission_id: str | int) -> dict[str, Any]:
    """Poll submission check until SUCCESS or 30s cap."""
    import time

    url: str = f"https://leetcode.com/submissions/detail/{submission_id}/check/"
    waited: float = 0.0
    last: dict[str, Any] = {"state": "PENDING"}
    while waited < 30.0:
        last = _get_json(url)
        if str(last.get("state")) == "SUCCESS":
            return last
        time.sleep(1.0)
        waited += 1.0
    return last


def leetcode_cli_fallback(args: list[str]) -> str:
    """Run leetcode-cli binary for repeated API failures."""
    import subprocess

    try:
        done = subprocess.run(
            ["leetcode", *args],
            capture_output=True,
            text=True,
            timeout=TIMEOUT,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("leetcode-cli not installed") from exc
    if done.returncode != 0:
        raise RuntimeError(f"leetcode-cli failed: {done.stderr.strip()}")
    return done.stdout
