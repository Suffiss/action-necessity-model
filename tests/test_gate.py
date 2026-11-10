import pytest
from _builders import act, read

from suffiss.necessity import ActionContext, ActionDecision, Decision, Evaluator, GateConfig, NecessityGate, ReasonCode


class FixedEvaluator(Evaluator):
    """Always returns the same verdict, so gate policy can be tested in isolation."""

    def __init__(self, verdict: Decision) -> None:
        super().__init__()
        self.verdict = verdict
        self.seen_history: list[int] = []

    def evaluate(self, context: ActionContext) -> ActionDecision:  # type: ignore[override]
        self.seen_history.append(len(context.history))
        return ActionDecision(self.verdict, 0.5, ReasonCode.INSUFFICIENT_CONTEXT, "fixed")


CALL = act("api_call", "weather_api", "Get weather", city="Tokyo")


def test_duplicate_read_is_skipped_and_counted() -> None:
    gate = NecessityGate("Fix typo in README")
    first, _ = gate.run(read("README.md"), execute=lambda a: "# Projcet")
    second, result = gate.run(read("README.md"), execute=lambda a: pytest.fail("must not execute"))
    assert first.allow and not second.allow
    assert second.why == "DUPLICATE_ACTION" and result is None
    assert gate.stats.to_dict() == {
        "proposed": 2, "allowed": 1, "skipped": 1, "saved_ratio": 0.5, "skipped_by_reason": {"DUPLICATE_ACTION": 1},
    }  # fmt: skip


def test_run_records_only_executed_actions() -> None:
    gate = NecessityGate("Fix typo in README")
    gate.run(read("README.md"), execute=lambda a: "text")
    gate.run(read("README.md"), execute=lambda a: "text")
    assert len(gate.history) == 1
    assert gate.history[0].result == "text"


def test_check_alone_does_not_change_history() -> None:
    gate = NecessityGate("Fix typo in README")
    gate.check(read("README.md"))
    assert gate.history == ()
    assert gate.stats.proposed == 1


def test_uncertain_actions_execute_by_default() -> None:
    gate = NecessityGate("g", evaluator=FixedEvaluator(Decision.UNCERTAIN))
    assert gate.check(CALL).allow


def test_uncertain_actions_can_be_skipped_by_policy() -> None:
    gate = NecessityGate("g", evaluator=FixedEvaluator(Decision.UNCERTAIN), config=GateConfig(uncertain_policy="skip"))
    verdict = gate.check(CALL)
    assert not verdict.allow and verdict.why == "UNCERTAIN_SKIPPED_BY_POLICY"


def test_retry_budget_caps_identical_uncertain_actions() -> None:
    gate = NecessityGate("g", evaluator=FixedEvaluator(Decision.UNCERTAIN), config=GateConfig(max_uncertain_repeats=2))
    allowed = [gate.run(CALL, execute=lambda a: "timeout")[0].allow for _ in range(4)]
    assert allowed == [True, True, False, False]
    assert gate.stats.skipped_by_reason == {"UNCERTAIN_RETRY_BUDGET_EXHAUSTED": 2}


def test_retry_budget_is_per_action_and_can_be_disabled() -> None:
    gate = NecessityGate("g", evaluator=FixedEvaluator(Decision.UNCERTAIN), config=GateConfig(max_uncertain_repeats=1))
    other = act("api_call", "weather_api", "Get weather", city="Paris")
    assert gate.run(CALL, execute=str)[0].allow and gate.run(other, execute=str)[0].allow
    assert not gate.run(CALL, execute=str)[0].allow
    unlimited = NecessityGate("g", evaluator=FixedEvaluator(Decision.UNCERTAIN), config=GateConfig(max_uncertain_repeats=None))
    assert all(unlimited.run(CALL, execute=str)[0].allow for _ in range(5))


def test_gate_passes_its_history_to_the_evaluator() -> None:
    evaluator = FixedEvaluator(Decision.NECESSARY)
    gate = NecessityGate("g", evaluator=evaluator)
    for _ in range(3):
        gate.run(CALL, execute=lambda a: "ok")
    assert evaluator.seen_history == [0, 1, 2]


def test_reported_state_change_unblocks_a_repeat() -> None:
    search = act("search", "grep", "Search for TODO markers", query="TODO", path="src")
    gate = NecessityGate("List remaining TODO markers in src")
    gate.run(search, execute=lambda a: "src/a.py:3: TODO")
    assert not gate.check(search).allow
    gate.update_state("Files in src were modified by another process.")
    assert gate.check(search).allow


@pytest.mark.parametrize("kwargs", [{"uncertain_policy": "maybe"}, {"max_uncertain_repeats": 0}])
def test_invalid_gate_config_is_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        GateConfig(**kwargs)


def test_saved_ratio_is_zero_before_any_proposal() -> None:
    assert NecessityGate("g").stats.saved_ratio == 0.0
