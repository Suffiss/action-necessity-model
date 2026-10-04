from pathlib import Path

import pytest

from simulations.runner import DEFAULT_TRAJECTORIES, format_results, load_trajectories, simulate
from suffiss.necessity import ActionContext, ActionDecision, Decision, Evaluator, ReasonCode

VERDICTS = {"keep": Decision.NECESSARY, "drop": Decision.UNNECESSARY, "maybe": Decision.UNCERTAIN}


class ScriptedEvaluator(Evaluator):
    """Decides from the action description so the accounting can be checked exactly."""

    def __init__(self) -> None:
        super().__init__()
        self.history_lengths: list[int] = []

    def evaluate(self, context: ActionContext) -> ActionDecision:  # type: ignore[override]
        self.history_lengths.append(len(context.history))
        verdict = VERDICTS[context.proposed_action.description]
        return ActionDecision(verdict, 0.9, ReasonCode.DIRECT_GOAL_DEPENDENCY, "scripted")


def _trajectory() -> dict:
    steps = [("keep", True), ("drop", False), ("maybe", False), ("drop", True)]
    return {
        "id": "t",
        "category": "test",
        "goal": "g",
        "steps": [{"action": {"type": "x", "description": d}, "result": "r", "essential": e} for d, e in steps],
    }


def test_execute_policy_accounting() -> None:
    evaluator = ScriptedEvaluator()
    result = simulate(_trajectory(), evaluator, policy="execute")
    assert (result.actions_before, result.actions_after, result.actions_saved) == (4, 2, 2)
    assert result.percentage_saved == pytest.approx(0.5)
    assert result.minimal_actions == 2
    assert result.skipped_essential == [4]
    assert result.successful_outcome_still_possible is False
    # Skipped steps never enter the history seen by later steps.
    assert evaluator.history_lengths == [0, 1, 1, 2]


def test_skip_policy_drops_uncertain_steps() -> None:
    result = simulate(_trajectory(), ScriptedEvaluator(), policy="skip")
    assert result.actions_after == 1


def test_shipped_trajectories_load_and_cover_required_categories() -> None:
    trajectories = load_trajectories(DEFAULT_TRAJECTORIES)
    assert len(trajectories) >= 5
    assert {t["category"] for t in trajectories} >= {"coding", "research", "file_editing", "tool_calling", "debugging"}


def test_report_lists_totals_for_real_trajectories() -> None:
    results = [simulate(t, Evaluator()) for t in load_trajectories(DEFAULT_TRAJECTORIES)]
    report = format_results(results, "execute")
    assert "Total actions" in report
    assert "Trajectories still successful" in report


def test_invalid_trajectory_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "t.jsonl"
    path.write_text('{"id": "t", "category": "c", "goal": "g", "steps": [{"action": {}}]}', encoding="utf-8")
    with pytest.raises(ValueError):
        load_trajectories(path)
