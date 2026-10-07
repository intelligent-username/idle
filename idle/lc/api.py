"""LeetCode API client and GraphQL interface."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any
import urllib.request

from idle import config
from idle.db import get_db
from idle.lc import auth

GRAPHQL_URL = "https://leetcode.com/graphql"


class AuthExpiredError(RuntimeError):
    """Raised when authentication expires or credentials are invalid."""
    pass


def _headers(slug: str | None = None) -> dict[str, str]:
    headers = auth.auth_headers()
    if slug:
        headers["Referer"] = f"https://leetcode.com/problems/{slug}/"
    return headers


def _post_json(url: str, payload: dict[str, Any], slug: str | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url)
    for k, v in _headers(slug).items():
        req.add_header(k, v)
    req.add_header("Content-Type", "application/json")
    data_bytes = json.dumps(payload).encode("utf-8")
    req.data = data_bytes
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res


def _get_json(url: str, slug: str | None = None) -> dict[str, Any]:
    req = urllib.request.Request(url)
    for k, v in _headers(slug).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode("utf-8"))
        return res


def _load_cached_problems(conn: Any = None) -> list[dict[str, Any]] | None:
    """Load problems cached in SQLite DB if fresh (<7 days)."""
    close_conn = False
    if conn is None:
        db_path, _, _ = config.resolve_paths()
        conn = get_db(db_path)
        close_conn = True

    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, slug, title, difficulty, tags_json, cached_at FROM lc_problems")
        rows = cursor.fetchall()
        if not rows:
            return None
        cached_at_str = rows[0][5]
        if cached_at_str:
            try:
                dt = datetime.fromisoformat(cached_at_str.replace("Z", "+00:00"))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                now = datetime.now(timezone.utc)
                if (now - dt).total_seconds() >= 7 * 86400:
                    return None
            except Exception:
                pass
        res = []
        for row in rows:
            res.append({
                "id": str(row[0]),
                "slug": row[1],
                "title": row[2],
                "difficulty": row[3],
                "tags": json.loads(row[4]) if row[4] else [],
            })
        return res
    except Exception:
        return None
    finally:
        if close_conn:
            conn.close()


def _save_problems(conn: Any, problems: list[dict[str, Any]]) -> None:
    """Upsert problems into SQLite DB cache."""
    now_iso = datetime.now(timezone.utc).isoformat()
    seq = []
    for item in problems:
        tags = item.get("tags", [])
        seq.append((str(item["id"]), item["slug"], item["title"], item["difficulty"], json.dumps(tags), now_iso))
    conn.execute("DELETE FROM lc_problems")
    conn.executemany(
        "INSERT INTO lc_problems (id, slug, title, difficulty, tags_json, cached_at) VALUES (?, ?, ?, ?, ?, ?)",
        seq,
    )
    conn.commit()


def fetch_problem_list(refresh: bool = False) -> list[dict[str, Any]]:
    """Fetch problem list from LeetCode or local DB cache."""
    db_path, _, _ = config.resolve_paths()
    conn = get_db(db_path)
    try:
        if not refresh:
            cached = _load_cached_problems(conn)
            if cached is not None:
                return cached
    finally:
        conn.close()

    total = None
    skip = 0
    limit = 100
    all_questions: list[dict[str, Any]] = []

    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
      ) {
        total: totalNum
        questions: data {
          acRate
          difficulty
          frontendQuestionId: questionFrontendId
          title
          titleSlug
          topicTags { name }
          status
        }
      }
    }
    """

    while total is None or len(all_questions) < total:
        payload = {
            "operationName": "problemsetQuestionList",
            "query": query,
            "variables": {
                "categorySlug": "all-code-essentials",
                "filters": {},
                "limit": limit,
                "skip": skip,
            },
        }
        resp = _post_json(GRAPHQL_URL, payload)
        data = resp.get("data", {}).get("problemsetQuestionList", {})
        total = data.get("total", 0)
        questions = data.get("questions", [])
        if not questions:
            break

        for q in questions:
            item_id = str(q.get("frontendQuestionId", ""))
            all_questions.append({
                "id": item_id,
                "slug": q.get("titleSlug", ""),
                "title": q.get("title", ""),
                "difficulty": q.get("difficulty", "Easy"),
                "tags": [t.get("name", "").lower() for t in q.get("topicTags", [])],
                "ac_rate": q.get("acRate", 0.0),
                "status": q.get("status"),
            })
        skip += len(questions)

    save_conn = get_db(db_path)
    try:
        _save_problems(save_conn, all_questions)
    finally:
        save_conn.close()

    return all_questions


def fetch_question(slug: str) -> dict[str, Any]:
    """Fetch detail for a question by slug."""
    query = """
    query questionData($titleSlug: String!) {
      question(titleSlug: $titleSlug) {
        questionId
        questionFrontendId
        title
        titleSlug
        content
        sampleTestCase
        codeSnippets {
          lang
          langSlug
          code
        }
      }
    }
    """
    payload = {
        "operationName": "questionData",
        "query": query,
        "variables": {"titleSlug": slug},
    }
    resp = _post_json(GRAPHQL_URL, payload, slug=slug)
    q = resp.get("data", {}).get("question", {})
    code_snippets: dict[str, str] = {}
    for s in q.get("codeSnippets", []):
        code_snippets[s.get("langSlug", "")] = s.get("code", "")

    return {
        "id": str(q.get("questionFrontendId", "")),
        "slug": q.get("titleSlug", slug),
        "title": q.get("title", ""),
        "content": q.get("content", ""),
        "sample_test_case": q.get("sampleTestCase", ""),
        "code_snippets": code_snippets,
    }


def fetch_daily() -> dict[str, Any]:
    """Fetch active daily coding challenge."""
    query = """
    query questionOfToday {
      activeDailyCodingChallengeQuestion {
        date
        link
        question {
          titleSlug
        }
      }
    }
    """
    payload = {"query": query}
    resp = _post_json(GRAPHQL_URL, payload)
    active = resp.get("data", {}).get("activeDailyCodingChallengeQuestion", {})
    question = active.get("question", {})
    slug = question.get("titleSlug")
    if not slug:
        raise RuntimeError("daily challenge not found")

    detail = fetch_question(slug)
    detail["link"] = active.get("link", f"/problems/{slug}/")
    return detail


def run_sample(slug: str, question_id: str, code: str, data_input: str) -> dict[str, Any]:
    """Run code against sample test cases."""
    url = f"https://leetcode.com/problems/{slug}/interpret_solution/"
    payload = {
        "lang": "python3",
        "question_id": question_id,
        "typed_code": code,
        "data_input": data_input,
    }
    res = _post_json(url, payload, slug=slug)
    if "interpretId" in res:
        res["interpret_id"] = res["interpretId"]
    return res


def submit_solution(slug: str, question_id: str, code: str) -> dict[str, Any]:
    """Submit solution code."""
    url = f"https://leetcode.com/problems/{slug}/submit/"
    payload = {
        "lang": "python3",
        "question_id": question_id,
        "typed_code": code,
    }
    res = _post_json(url, payload, slug=slug)
    if "submissionId" in res:
        res["submission_id"] = res["submissionId"]
    return res


def poll_verdict(submission_id: int | str, timeout_s: float = 5.0) -> dict[str, Any]:
    """Poll submission verdict by submission_id until non-PENDING or retries exhausted."""
    url = f"https://leetcode.com/submissions/detail/{submission_id}/check/"
    res: dict[str, Any] = {}
    for _ in range(5):
        res = _get_json(url)
        if res.get("state") != "PENDING":
            break
    return res


def run_local(code: str, data_input: str, expected_output: str = "") -> dict[str, Any]:
    """Execute solution locally without network."""
    loc: dict[str, Any] = {}
    try:
        exec(code, loc)
        sol_cls = loc.get("Solution")
        if not sol_cls:
            return {"status_msg": "Runtime Error", "error": "No Solution class found"}

        inst = sol_cls()
        methods = [m for m in dir(inst) if not m.startswith("_")]
        if not methods:
            return {"status_msg": "Runtime Error", "error": "No methods found"}

        method = getattr(inst, methods[0])
        arg_val = eval(data_input)
        if isinstance(arg_val, tuple):
            res = method(*arg_val)
        else:
            res = method(arg_val)

        return {
            "status_msg": "Accepted",
            "state": "SUCCESS",
            "result": str(res),
        }
    except Exception as e:
        return {
            "status_msg": "Runtime Error",
            "error": str(e),
            "state": "FAILURE",
        }
