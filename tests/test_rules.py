import pytest

from suffiss.necessity.models import Action
from suffiss.necessity.rules import (
    ActionKind,
    ResultStatus,
    classify_action,
    classify_result,
    is_doc_path,
    is_mutating,
    is_truncated,
    mentions_target,
)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ("", ResultStatus.UNKNOWN),
        ("===== 42 passed, 0 failed in 1.2s =====", ResultStatus.SUCCESS),
        ("1 failed, 41 passed", ResultStatus.FAILURE),
        ("exit_code=0", ResultStatus.SUCCESS),
        ("exited with code 2", ResultStatus.FAILURE),
        ("Error: No such file or directory", ResultStatus.FAILURE),
        ("Request timed out after 30s", ResultStatus.TRANSIENT_FAILURE),
        ("HTTP 503 Service Unavailable", ResultStatus.TRANSIENT_FAILURE),
        ('{"status": 404}', ResultStatus.FAILURE),
        ('{"status": "running", "progress": 40}', ResultStatus.PENDING),
        # File content that merely mentions errors is not a failed read.
        ("def handle_error(exc):\n    log(exc)", ResultStatus.SUCCESS),
    ],
)
def test_classify_result(result: str, expected: ResultStatus) -> None:
    assert classify_result(result) is expected


@pytest.mark.parametrize(
    ("action", "kind", "mutating"),
    [
        (Action("file_read", "read_file"), ActionKind.READ, False),
        (Action("file_edit", "edit_file"), ActionKind.WRITE, True),
        (Action("search", "grep"), ActionKind.SEARCH, False),
        (Action("api_call", "http_get"), ActionKind.REQUEST, False),
        (Action("api_call", "http", arguments={"method": "POST"}), ActionKind.REQUEST, True),
        (Action("command", "run_shell", arguments={"command": "pytest -q"}), ActionKind.EXECUTE, False),
        (Action("command", "run_shell", arguments={"command": "npm install"}), ActionKind.EXECUTE, True),
        (Action("db", "sql", arguments={"query": "UPDATE users SET a=1"}), ActionKind.READ, True),
        (Action("db", "sql", arguments={"query": "SELECT id FROM users"}), ActionKind.READ, False),
        (Action("finish", "finish"), ActionKind.FINISH, False),
    ],
)
def test_classify_action(action: Action, kind: ActionKind, mutating: bool) -> None:
    assert classify_action(action) is kind
    assert is_mutating(action) is mutating


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("readme.md", True),
        ("docs/setup.py", True),
        ("license", True),
        ("notice", True),
        ("src/license.py", False),
        ("src/app.py", False),
    ],
)
def test_is_doc_path(path: str, expected: bool) -> None:
    assert is_doc_path(path) is expected


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ("80: (truncated, showing lines 1-80 of 200)", True),
        ("Showing results 21 to 40 of 97", True),
        ('{"items": [], "has_more": true}', True),
        ("Page 1 of 9", True),
        ("all 12 rows returned", False),
        ("untruncatedness is a made-up word", False),
    ],
)
def test_is_truncated(result: str, expected: bool) -> None:
    assert is_truncated(result) is expected


@pytest.mark.parametrize(
    ("result", "target", "expected"),
    [
        (r"src\cache.py:12: def evict()", "src/cache.py", True),
        ("1. Survey - arxiv.org/abs/2009.06732", "https://arxiv.org/abs/2009.06732", True),
        ("see www.example.com/docs", "https://www.example.com/docs", True),
        ("src/cache.py:12: def evict()", "src/other.py", False),
        ("a.b", "a.b", False),
    ],
)
def test_mentions_target(result: str, target: str, expected: bool) -> None:
    assert mentions_target(result, target) is expected
