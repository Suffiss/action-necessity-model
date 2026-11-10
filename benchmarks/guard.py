"""Regression guard: fail when dev-benchmark or simulation results fall below recorded floors.

Usage (from the repository root):  python -m benchmarks.guard

Only the development benchmark and the simulated trajectories are guarded.
The held-out set and the v1 test split stay out on purpose: checking them on
every change would quietly turn them into tuning sets.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.metrics import Metrics
from benchmarks.runner import DEFAULT_DATASET, load_cases, run_cases, summarize
from simulations.runner import DEFAULT_TRAJECTORIES, TrajectoryResult, load_trajectories, simulate
from suffiss.necessity import Evaluator

GUARDRAILS = Path(__file__).with_name("guardrails.json")
_EPSILON = 1e-9  # floors are written as exact fractions like 0.9 = 27/30


@dataclass(frozen=True)
class Violation:
    check: str
    actual: float
    limit: float

    def __str__(self) -> str:
        return f"{self.check}: {self.actual:.4f} (limit {self.limit:.4f})"


def _at_least(name: str, actual: float, floor: float) -> list[Violation]:
    return [] if actual >= floor - _EPSILON else [Violation(name, actual, floor)]


def _at_most(name: str, actual: float, ceiling: float) -> list[Violation]:
    return [] if actual <= ceiling + _EPSILON else [Violation(name, actual, ceiling)]


def check_dev(metrics: Metrics, limits: Mapping[str, float]) -> list[Violation]:
    return (
        _at_most("dev.false_unnecessary_rate", metrics.false_unnecessary_rate, limits["max_false_unnecessary_rate"])
        + _at_least("dev.accuracy", metrics.accuracy, limits["min_accuracy"])
        + _at_least("dev.unnecessary_action_detection_rate", metrics.unnecessary_action_detection_rate,
                    limits["min_unnecessary_action_detection_rate"])  # fmt: skip
    )


def simulation_summary(results: Sequence[TrajectoryResult]) -> dict[str, float]:
    before = sum(r.actions_before for r in results)
    return {
        "successful_trajectories_share": sum(r.successful_outcome_still_possible for r in results) / len(results),
        "saved_share": sum(r.actions_saved for r in results) / before,
        "skipped_essential_steps": sum(len(r.skipped_essential) for r in results),
    }


def check_simulation(summary: Mapping[str, float], limits: Mapping[str, Any]) -> list[Violation]:
    return (
        _at_least("simulation.successful_trajectories_share", summary["successful_trajectories_share"],
                  limits["min_successful_trajectories_share"])  # fmt: skip
        + _at_least("simulation.saved_share", summary["saved_share"], limits["min_saved_share"])
        + _at_most("simulation.skipped_essential_steps", summary["skipped_essential_steps"], limits["max_skipped_essential_steps"])
    )


def run_guard(guardrails: Path = GUARDRAILS, evaluator: Evaluator | None = None) -> tuple[list[Violation], dict[str, Any]]:
    limits = json.loads(guardrails.read_text(encoding="utf-8"))
    evaluator = evaluator or Evaluator()
    metrics = summarize(run_cases(load_cases(DEFAULT_DATASET), evaluator))
    policy = limits["simulation"]["uncertain_policy"]
    sim = simulation_summary([simulate(t, evaluator, policy) for t in load_trajectories(DEFAULT_TRAJECTORIES)])
    observed = {
        "dev": {"false_unnecessary_rate": metrics.false_unnecessary_rate, "accuracy": metrics.accuracy,
                "unnecessary_action_detection_rate": metrics.unnecessary_action_detection_rate},
        "simulation": sim,
    }  # fmt: skip
    return check_dev(metrics, limits["dev"]) + check_simulation(sim, limits["simulation"]), observed


def main(argv: Sequence[str] | None = None) -> int:
    violations, observed = run_guard()
    print(json.dumps(observed, indent=2))
    if violations:
        print("\nREGRESSION:", *[f"  {v}" for v in violations], sep="\n", file=sys.stderr)
        return 1
    print("\nAll guardrails hold.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
