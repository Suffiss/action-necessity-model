from _builders import act, edit, judge, read, rec

from suffiss.necessity.models import Decision, ReasonCode


def test_duplicate_file_read_is_unnecessary() -> None:
    decision = judge(
        "Fix typo in README",
        read("README.md"),
        history=[rec(read("README.md"), "# Projcet\nA tool.")],
    )
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.DUPLICATE_ACTION
    assert decision.signals.duplicate_action_probability > 0.9


def test_duplicate_search_is_unnecessary() -> None:
    search = act("search", "grep", "Search for parse_config", query="parse_config")
    decision = judge(
        "Find where parse_config is defined",
        search,
        history=[rec(search, "src/config.py:12: def parse_config(path):")],
    )
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.DUPLICATE_ACTION


def test_search_with_only_cosmetic_query_differences_is_duplicate() -> None:
    earlier = act("search", "web_search", "Search docs", query="python  dataclass Slots")
    proposed = act("search", "web_search", "Search docs again", query="Python dataclass slots")
    decision = judge(
        "Learn how dataclass slots work in Python",
        proposed,
        history=[rec(earlier, "Result: dataclass(slots=True) generates __slots__ ...")],
    )
    assert decision.decision is Decision.UNNECESSARY


def test_same_tool_with_meaningfully_different_arguments_is_not_duplicate() -> None:
    decision = judge(
        "Refactor the helper functions in src/a.py and src/b.py",
        read("src/b.py"),
        history=[rec(read("src/a.py"), "def helper(): ...")],
    )
    assert decision.decision is not Decision.UNNECESSARY
    assert decision.reason_code is not ReasonCode.DUPLICATE_ACTION
    assert decision.signals.duplicate_action_probability < 0.5


def test_editing_another_file_does_not_justify_rereading() -> None:
    decision = judge(
        "Rename helper in src/b.py",
        read("src/a.py"),
        history=[
            rec(read("src/a.py"), "import b"),
            rec(edit("src/b.py"), "ok"),
        ],
    )
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.DUPLICATE_ACTION


def test_queries_differing_only_in_operator_are_not_duplicates() -> None:
    earlier = act("db_query", "sql", "Count active users", query="SELECT count(*) FROM users WHERE age > 30")
    proposed = act("db_query", "sql", "Count active users", query="SELECT count(*) FROM users WHERE age < 30")
    decision = judge(
        "Compare user counts above and below age 30",
        proposed,
        history=[rec(earlier, "count: 120")],
    )
    assert decision.reason_code is not ReasonCode.DUPLICATE_ACTION
    assert decision.decision is not Decision.UNNECESSARY
