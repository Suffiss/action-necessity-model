import pytest
from _builders import act, judge, read, rec

from suffiss.necessity.adapters import AdapterAssessment
from suffiss.necessity.evaluator import Evaluator, EvaluatorConfig, Thresholds, evaluate_action
from suffiss.necessity.models import ActionContext, Decision, ReasonCode


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
