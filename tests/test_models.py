import pytest

from suffiss.necessity.models import (
    Action,
    ActionContext,
    ActionDecision,
    ActionRecord,
    ContextValidationError,
    Decision,
    ReasonCode,
    SignalScores,
)

CONTEXT_JSON = {
    "goal": "Fix typo in README",
    "current_state": "README not read yet",
    "history": [
        {
            "action": {
                "type": "file_read",
                "tool": "read_file",
                "description": "Read README.md",
                "arguments": {"path": "README.md"},
            },
            "result": "# Projcet",
        }
    ],
    "proposed_action": {
        "type": "file_edit",
        "tool": "edit_file",
        "description": "Fix typo",
        "arguments": {"path": "README.md"},
    },
}


def test_context_round_trips_through_dict() -> None:
    context = ActionContext.from_dict(CONTEXT_JSON)
    assert context.to_dict() == CONTEXT_JSON


def test_context_parses_nested_types() -> None:
    context = ActionContext.from_dict(CONTEXT_JSON)
    assert isinstance(context.history[0], ActionRecord)
    assert context.history[0].action == Action(
        type="file_read", tool="read_file", description="Read README.md", arguments={"path": "README.md"}
    )
    assert context.proposed_action.tool == "edit_file"


def test_optional_fields_default_to_empty() -> None:
    context = ActionContext.from_dict({"goal": "g", "proposed_action": {"type": "search"}})
    assert context.current_state == ""
    assert context.history == ()
    assert context.proposed_action.arguments == {}


@pytest.mark.parametrize(
    "payload",
    [
        "not a dict",
        {"goal": "g"},
        {"goal": 3, "proposed_action": {"type": "x"}},
        {"goal": "g", "history": "nope", "proposed_action": {"type": "x"}},
        {"goal": "g", "history": [{"result": "r"}], "proposed_action": {"type": "x"}},
        {"goal": "g", "proposed_action": {"type": "x", "arguments": ["a"]}},
        {"goal": "g", "proposed_action": {"type": None}},
    ],
)
def test_invalid_context_is_rejected(payload: object) -> None:
    with pytest.raises(ContextValidationError):
        ActionContext.from_dict(payload)


def test_signal_scores_reject_out_of_range_values() -> None:
    with pytest.raises(ValueError):
        SignalScores(goal_relevance=1.5)


def test_decision_serializes_with_stable_codes() -> None:
    decision = ActionDecision(
        decision=Decision.UNNECESSARY,
        confidence=0.9,
        reason_code=ReasonCode.DUPLICATE_ACTION,
        explanation="Same read already performed.",
    )
    payload = decision.to_dict()
    assert payload["decision"] == "unnecessary"
    assert payload["reason_code"] == "DUPLICATE_ACTION"
    assert set(payload["signals"]) == {
        "goal_relevance",
        "new_information_gain",
        "duplicate_action_probability",
        "task_completion_probability",
        "scope_alignment",
    }


def test_decision_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        ActionDecision(Decision.NECESSARY, 1.2, ReasonCode.STATE_CHANGED, "x")
