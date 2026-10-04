import pytest
from _builders import act, judge, read, rec

from suffiss.necessity.evaluator import evaluate_action
from suffiss.necessity.models import ContextValidationError, Decision, ReasonCode


@pytest.mark.parametrize("goal", ["", "   ", "help"])
def test_missing_or_vague_goal_is_uncertain(goal: str) -> None:
    decision = judge(goal, read("src/main.py"))
    assert decision.decision is Decision.UNCERTAIN
    assert decision.reason_code is ReasonCode.INSUFFICIENT_CONTEXT


def test_vague_proposed_action_is_uncertain() -> None:
    decision = judge("Fix the failing checkout flow", act("other", "", "do it"))
    assert decision.decision is Decision.UNCERTAIN
    assert decision.reason_code is ReasonCode.INSUFFICIENT_CONTEXT


def test_polling_a_pending_job_is_not_blocked() -> None:
    poll = act("api_call", "http_get", "Check build status", url="https://ci.example.com/builds/17")
    decision = judge(
        "Wait for build 17 to finish and report the result",
        poll,
        history=[rec(poll, '{"status": "running", "progress": 40}')],
    )
    assert decision.decision is not Decision.UNNECESSARY


def test_state_snapshot_reporting_change_unblocks_repeat() -> None:
    search = act("search", "grep", "Search for TODO markers", query="TODO", path="src")
    decision = judge(
        "List remaining TODO markers in src",
        search,
        history=[rec(search, "src/a.py:3: TODO")],
        state="Files in src were modified by another process since the last search.",
    )
    assert decision.decision is not Decision.UNNECESSARY


def test_negated_change_in_state_does_not_unblock_repeat() -> None:
    search = act("search", "grep", "Search for TODO markers", query="TODO", path="src")
    decision = judge(
        "List remaining TODO markers in src",
        search,
        history=[rec(search, "src/a.py:3: TODO")],
        state="Nothing has changed since the last search.",
    )
    assert decision.decision is Decision.UNNECESSARY


def test_malformed_input_raises_validation_error() -> None:
    with pytest.raises(ContextValidationError):
        evaluate_action({"goal": "x", "proposed_action": "read file"})
