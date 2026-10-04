import pytest
from _builders import act, judge, read, rec

from suffiss.necessity.adapters import AdapterAssessment
from suffiss.necessity.evaluator import Evaluator, EvaluatorConfig, Thresholds, evaluate_action
from suffiss.necessity.features import extract_features
from suffiss.necessity.models import ActionContext, Decision, ReasonCode
from suffiss.necessity.similarity import LexicalSimilarity


def test_overly_broad_action_for_narrow_goal_is_unnecessary() -> None:
    decision = judge(
        "Fix button padding on the login page",
        act("index", "index_repository", "Index the entire repository", path="."),
    )
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.SCOPE_TOO_BROAD
    assert decision.signals.scope_alignment < 0.5


def test_broad_action_for_broad_goal_is_not_blocked() -> None:
    decision = judge(
        "Find all usages of the deprecated fetch_user API across the codebase",
        act("search", "grep", "Search the entire repository for fetch_user", query="fetch_user", path="."),
    )
    assert decision.decision is not Decision.UNNECESSARY


def test_reading_config_before_modifying_it_is_necessary() -> None:
    decision = judge(
        "Modify config safely to raise the request timeout",
        read("config.yaml"),
        state="The config file has not been read yet.",
    )
    assert decision.decision is Decision.NECESSARY
    assert decision.reason_code in {ReasonCode.PREREQUISITE_ACTION, ReasonCode.NEW_INFORMATION_REQUIRED}


def test_unrelated_action_is_unnecessary() -> None:
    decision = judge(
        "Fix typo in README",
        act("file_list", "list_files", "Inspect database migrations", path="db/migrations"),
    )
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.LOW_GOAL_RELEVANCE
    assert decision.signals.goal_relevance < 0.3


def test_gathering_missing_information_is_necessary() -> None:
    decision = judge(
        "Find why the application crashed",
        read("logs/error.log"),
        state="No logs have been inspected yet.",
    )
    assert decision.decision is Decision.NECESSARY
    assert decision.reason_code is ReasonCode.NEW_INFORMATION_REQUIRED
    assert decision.signals.new_information_gain > 0.5


def test_decision_output_contract() -> None:
    decision = judge("Fix typo in README", read("README.md"))
    payload = decision.to_dict()
    assert payload["decision"] in {"necessary", "unnecessary", "uncertain"}
    assert 0.0 <= payload["confidence"] <= 1.0
    assert all(0.0 <= value <= 1.0 for value in payload["signals"].values())
    assert payload["explanation"]


def test_accepts_typed_context_and_dict_equally() -> None:
    raw = {"goal": "Fix typo in README", "proposed_action": read("README.md")}
    assert evaluate_action(raw) == evaluate_action(ActionContext.from_dict(raw))


def test_thresholds_are_configurable() -> None:
    # A duplicate read with some goal relevance scores low but not zero.
    context = {
        "goal": "Fix typo in README",
        "history": [rec(read("README.md"), "# Projcet")],
        "proposed_action": read("README.md"),
    }
    assert evaluate_action(context).decision is Decision.UNNECESSARY
    strict = Evaluator(EvaluatorConfig(thresholds=Thresholds(necessary=0.99, unnecessary=0.01)))
    assert strict.evaluate(context).decision is Decision.UNCERTAIN


def test_adapter_opinion_is_blended_into_score() -> None:
    class AlwaysNecessary:
        name = "stub"

        def assess(self, context: ActionContext) -> AdapterAssessment:
            return AdapterAssessment(necessity=1.0, weight=1.0)

    context = {
        "goal": "Fix typo in README",
        "history": [rec(read("README.md"), "# Projcet")],
        "proposed_action": read("README.md"),
    }
    blended = Evaluator(EvaluatorConfig(adapter=AlwaysNecessary()))
    assert blended.evaluate(context).decision is Decision.NECESSARY


def test_invalid_thresholds_are_rejected() -> None:
    with pytest.raises(ValueError):
        Thresholds(necessary=0.3, unnecessary=0.6)


def test_evaluation_is_deterministic() -> None:
    context = {
        "goal": "Fix typo in README",
        "history": [rec(read("README.md"), "# Projcet")],
        "proposed_action": read("README.md"),
    }
    assert evaluate_action(context) == evaluate_action(context)


def test_relevance_counts_the_goal_clause_the_action_serves() -> None:
    decision = judge(
        "Archive the stale support tickets and export the quarterly report",
        act("browser", "navigate", "Open the export page", url="https://crm.example.com/export"),
    )
    assert decision.signals.goal_relevance >= 0.3
    assert decision.decision is not Decision.UNNECESSARY


def test_paging_through_truncated_output_is_necessary() -> None:
    first = act("api_call", "list_tickets", "List open tickets", status="open", page=1)
    decision = judge(
        "Count the open tickets assigned to nobody",
        act("api_call", "list_tickets", "List open tickets", status="open", page=2),
        history=[rec(first, "Showing items 1-50 of 212\n#101 unassigned\n...")],
    )
    assert decision.decision is Decision.NECESSARY
    assert decision.reason_code is ReasonCode.NEW_INFORMATION_REQUIRED


@pytest.mark.parametrize(("result", "expected"), [("Showing items 1-50 of 212", True), ("#101 unassigned", False)])
def test_continuation_requires_an_explicitly_truncated_result(result: str, expected: bool) -> None:
    first = act("api_call", "list_tickets", "List open tickets", status="open", page=1)
    context = ActionContext.from_dict(
        {
            "goal": "Count the open tickets assigned to nobody",
            "history": [rec(first, result)],
            "proposed_action": act("api_call", "list_tickets", "List open tickets", status="open", page=2),
        }
    )
    assert extract_features(context, LexicalSimilarity(), 0.95).continuation is expected


def test_following_a_lead_from_search_results_is_necessary() -> None:
    decision = judge(
        "Find the cause of the memory leak",
        read("workers/pool.py"),
        history=[rec(act("search", "grep", "Search for leak", query="leak"), "workers/pool.py:88: # FIXME: leak on retry")],
    )
    assert decision.decision is Decision.NECESSARY
    assert decision.reason_code is ReasonCode.NEW_INFORMATION_REQUIRED


def test_rereading_a_lead_already_followed_is_still_duplicate() -> None:
    decision = judge(
        "Find the cause of the memory leak",
        read("workers/pool.py"),
        history=[
            rec(act("search", "grep", "Search for leak", query="leak"), "workers/pool.py:88: # FIXME: leak on retry"),
            rec(read("workers/pool.py"), "class Pool: ..."),
        ],
    )
    assert decision.decision is Decision.UNNECESSARY


def test_rereading_a_log_full_of_errors_is_a_duplicate_not_a_retry() -> None:
    log = "2026-10-01 ERROR db pool exhausted\nTraceback (most recent call last): ..."
    decision = judge(
        "Find why the worker keeps restarting",
        read("logs/worker.log"),
        history=[rec(read("logs/worker.log"), log)],
    )
    assert decision.decision is Decision.UNNECESSARY
    assert decision.reason_code is ReasonCode.DUPLICATE_ACTION


def test_a_write_is_never_labelled_a_prerequisite_read() -> None:
    decision = judge(
        "Remove inactive sessions from the sessions table",
        act("db_query", "sql", "Delete inactive sessions", query="DELETE FROM sessions WHERE active = false"),
        history=[rec(act("db_query", "sql", "Count inactive", query="SELECT COUNT(*) FROM sessions WHERE active = false"), "count: 9")],
    )
    assert decision.reason_code is not ReasonCode.PREREQUISITE_ACTION


def test_editing_a_file_surfaced_by_search_acts_on_the_lead() -> None:
    decision = judge(
        "Find why the nightly sync crashed and fix it",
        act("file_edit", "edit_file", "Skip rows without an id", path="workers/sync.py", old="row['id']", new="row.get('id')"),
        history=[rec(act("search", "grep", "Search for KeyError", query="KeyError"), "workers/sync.py:12: KeyError: 'id'")],
    )
    assert decision.decision is Decision.NECESSARY
    assert decision.reason_code is ReasonCode.DIRECT_GOAL_DEPENDENCY
