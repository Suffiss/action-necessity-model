"""The regression guard: unit checks, the real results, and proof it catches a regression."""

import json
from pathlib import Path

import pytest

from benchmarks.guard import GUARDRAILS, Violation, check_dev, check_simulation, run_guard
from benchmarks.metrics import compute_metrics
from suffiss.necessity import ActionContext, ActionDecision, Decision, Evaluator, EvaluatorConfig, ReasonCode, Thresholds

DEV_LIMITS = {"max_false_unnecessary_rate": 0.0, "min_accuracy": 0.9, "min_unnecessary_action_detection_rate": 0.85}
SIM_LIMITS = {"min_successful_trajectories_share": 1.0, "min_saved_share": 0.3, "max_skipped_essential_steps": 0}


def test_current_results_hold_every_guardrail() -> None:
    violations, observed = run_guard()
    assert violations == [], [str(v) for v in violations]
    assert observed["dev"]["false_unnecessary_rate"] == 0.0


class BlocksEverything(Evaluator):
    def evaluate(self, context: ActionContext) -> ActionDecision:  # type: ignore[override]
        return ActionDecision(Decision.UNNECESSARY, 0.9, ReasonCode.DUPLICATE_ACTION, "blocked")


def test_guard_catches_an_evaluator_that_blocks_needed_work() -> None:
    violations, _ = run_guard(evaluator=BlocksEverything())
    checks = {v.check for v in violations}
    assert {"dev.false_unnecessary_rate", "dev.accuracy", "simulation.skipped_essential_steps"} <= checks


def test_guard_catches_a_milder_threshold_regression() -> None:
    # Over-eager thresholds still pass the dev safety floor here, but the simulation catches them.
    eager = Evaluator(EvaluatorConfig(thresholds=Thresholds(necessary=0.99, unnecessary=0.98)))
    checks = {v.check for v in run_guard(evaluator=eager)[0]}
    assert "simulation.skipped_essential_steps" in checks


def test_exact_floors_pass() -> None:
    # 27/30 is exactly 0.9: float rounding must not fail it.
    expected = ["necessary"] * 27 + ["unnecessary"] * 3
    predicted = ["necessary"] * 27 + ["necessary"] * 3
    metrics = compute_metrics(expected, predicted)
    assert metrics.accuracy == pytest.approx(0.9)
    assert [v.check for v in check_dev(metrics, {**DEV_LIMITS, "min_unnecessary_action_detection_rate": 0.0})] == []


def test_dev_checks_report_each_breach() -> None:
    metrics = compute_metrics(["necessary", "unnecessary"], ["unnecessary", "necessary"])
    assert {v.check for v in check_dev(metrics, DEV_LIMITS)} == {
        "dev.false_unnecessary_rate", "dev.accuracy", "dev.unnecessary_action_detection_rate",
    }  # fmt: skip


def test_simulation_checks() -> None:
    healthy = {"successful_trajectories_share": 1.0, "saved_share": 0.31, "skipped_essential_steps": 0}
    assert check_simulation(healthy, SIM_LIMITS) == []
    broken = {"successful_trajectories_share": 0.5, "saved_share": 0.2, "skipped_essential_steps": 3}
    assert len(check_simulation(broken, SIM_LIMITS)) == 3


def test_violation_message_names_the_check() -> None:
    assert str(Violation("dev.accuracy", 0.8, 0.9)) == "dev.accuracy: 0.8000 (limit 0.9000)"


def test_guardrails_never_cover_held_out_or_v1_test_sets() -> None:
    limits = json.loads(Path(GUARDRAILS).read_text(encoding="utf-8"))
    assert set(limits) - {"_comment"} == {"dev", "simulation"}
