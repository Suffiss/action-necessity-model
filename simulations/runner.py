"""Replay labelled agent trajectories through the gate and measure savings.

Each step is proposed to the gate in order. Executed steps (and their recorded
results) enter the history; skipped steps never happen, so later decisions see
exactly what a gated agent would have seen. A run stays successful only if
every step labelled ``essential`` was executed.

Usage (from the repository root):  python -m simulations.runner [trajectories.jsonl]
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Sequence

from suffiss.necessity import ActionContext, Decision, Evaluator

DEFAULT_TRAJECTORIES = Path(__file__).with_name("trajectories.jsonl")
UncertainPolicy = Literal["execute", "skip"]
POLICIES: tuple[UncertainPolicy, ...] = ("execute", "skip")


@dataclass(frozen=True)
class StepOutcome:
    index: int
    description: str
    decision: str
    reason_code: str
    executed: bool
    essential: bool


@dataclass(frozen=True)
class TrajectoryResult:
    id: str
    category: str
    steps: tuple[StepOutcome, ...]

    @property
    def actions_before(self) -> int:
        return len(self.steps)

    @property
    def actions_after(self) -> int:
        return sum(1 for s in self.steps if s.executed)

    @property
    def actions_saved(self) -> int:
        return self.actions_before - self.actions_after

    @property
    def percentage_saved(self) -> float:
        return self.actions_saved / self.actions_before if self.actions_before else 0.0

    @property
    def minimal_actions(self) -> int:
        return sum(1 for s in self.steps if s.essential)

    @property
    def skipped_essential(self) -> list[int]:
        return [s.index for s in self.steps if s.essential and not s.executed]

    @property
    def successful_outcome_still_possible(self) -> bool:
        return not self.skipped_essential


def load_trajectories(path: Path) -> list[dict[str, Any]]:
    trajectories = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for trajectory in trajectories:
        for field in ("id", "category", "goal", "steps"):
            if field not in trajectory:
                raise ValueError(f"trajectory {trajectory.get('id', '?')} is missing '{field}'")
        for number, step in enumerate(trajectory["steps"], start=1):
            if "action" not in step or not isinstance(step.get("essential"), bool):
                raise ValueError(f"{trajectory['id']} step {number} needs 'action' and boolean 'essential'")
    return trajectories


def simulate(trajectory: dict[str, Any], evaluator: Evaluator, policy: UncertainPolicy = "execute") -> TrajectoryResult:
    history: list[dict[str, Any]] = []
    state = trajectory.get("initial_state", "")
    outcomes = []
    for index, step in enumerate(trajectory["steps"], start=1):
        state = step.get("state", state)
        context = {"goal": trajectory["goal"], "current_state": state, "history": history, "proposed_action": step["action"]}
        decision = evaluator.evaluate(ActionContext.from_dict(context))
        executed = _should_execute(decision.decision, policy)
        if executed:
            history = [*history, {"action": step["action"], "result": step.get("result", "")}]
        outcomes.append(
            StepOutcome(
                index=index,
                description=step["action"].get("description", ""),
                decision=decision.decision.value,
                reason_code=decision.reason_code.value,
                executed=executed,
                essential=step["essential"],
            )
        )
    return TrajectoryResult(id=trajectory["id"], category=trajectory["category"], steps=tuple(outcomes))


def _should_execute(decision: Decision, policy: UncertainPolicy) -> bool:
    if decision is Decision.UNCERTAIN:
        return policy == "execute"
    return decision is Decision.NECESSARY


def format_results(results: Sequence[TrajectoryResult], policy: UncertainPolicy) -> str:
    lines = [f"Uncertain policy: {policy}", ""]
    lines.append(f"{'trajectory':<32} {'before':>6} {'after':>6} {'minimal':>7} {'saved':>6} {'saved%':>7}  success_possible")
    for r in results:
        lines.append(
            f"{r.id:<32} {r.actions_before:>6} {r.actions_after:>6} {r.minimal_actions:>7} {r.actions_saved:>6} "
            f"{r.percentage_saved:>7.1%}  {r.successful_outcome_still_possible}"
        )
    before = sum(r.actions_before for r in results)
    after = sum(r.actions_after for r in results)
    avoidable = before - sum(r.minimal_actions for r in results)
    saved_avoidable = sum(1 for r in results for s in r.steps if not s.essential and not s.executed)
    lines += [
        "",
        f"Total actions: {before} -> {after} (saved {before - after}, {(before - after) / before:.1%})",
        f"Avoidable actions removed: {saved_avoidable}/{avoidable}",
        f"Trajectories still successful: {sum(r.successful_outcome_still_possible for r in results)}/{len(results)}",
    ]
    for r in results:
        if r.skipped_essential:
            lines.append(f"  ! {r.id}: essential steps skipped {r.skipped_essential}")
    return "\n".join(lines)


def format_step_log(results: Sequence[TrajectoryResult]) -> str:
    lines = []
    for r in results:
        lines.append(f"{r.id}:")
        for s in r.steps:
            mark = "run " if s.executed else "SKIP"
            tag = "essential" if s.essential else "avoidable"
            lines.append(f"  {s.index}. [{mark}] {s.decision:<11} {s.reason_code:<26} ({tag}) {s.description}")
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    verbose = "--steps" in args
    paths = [arg for arg in args if not arg.startswith("--")]
    trajectories = load_trajectories(Path(paths[0]) if paths else DEFAULT_TRAJECTORIES)
    evaluator = Evaluator()
    for policy in POLICIES:
        results = [simulate(t, evaluator, policy) for t in trajectories]
        print(format_results(results, policy))
        if verbose:
            print("\n" + format_step_log(results))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
