"""A small stateful helper that puts the evaluator in front of an agent's tool calls.

    gate = NecessityGate(goal="Fix typo in README")
    for action in plan:
        verdict, result = gate.run(action, execute=call_tool)

The gate keeps the history the evaluator needs, applies a policy to
``uncertain`` decisions, caps blind retries, and counts what it saved.
It never executes anything itself: ``run`` calls the function you pass.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Mapping

from suffiss.necessity.evaluator import Evaluator
from suffiss.necessity.models import Action, ActionContext, ActionDecision, ActionRecord, Decision
from suffiss.necessity.similarity import normalize_arguments, normalize_text

UncertainPolicy = Literal["execute", "skip"]
ActionLike = Action | Mapping[str, Any]


@dataclass(frozen=True)
class GateConfig:
    # Executing uncertain actions keeps task success safe; skipping them saved more
    # but broke half the simulated trajectories (simulations/RESULTS.md).
    uncertain_policy: UncertainPolicy = "execute"
    # How many times an identical action may run while the gate is unsure about it.
    # None means no cap. This bounds blind retries of flaky calls.
    max_uncertain_repeats: int | None = 2

    def __post_init__(self) -> None:
        if self.uncertain_policy not in ("execute", "skip"):
            raise ValueError("uncertain_policy must be 'execute' or 'skip'")
        if self.max_uncertain_repeats is not None and self.max_uncertain_repeats < 1:
            raise ValueError("max_uncertain_repeats must be at least 1, or None")


@dataclass(frozen=True)
class GateVerdict:
    allow: bool
    decision: ActionDecision
    why: str


@dataclass
class GateStats:
    proposed: int = 0
    allowed: int = 0
    skipped: int = 0
    skipped_by_reason: Counter[str] = field(default_factory=Counter)

    @property
    def saved_ratio(self) -> float:
        return self.skipped / self.proposed if self.proposed else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposed": self.proposed,
            "allowed": self.allowed,
            "skipped": self.skipped,
            "saved_ratio": round(self.saved_ratio, 4),
            "skipped_by_reason": dict(self.skipped_by_reason),
        }


def _as_action(action: ActionLike) -> Action:
    return action if isinstance(action, Action) else Action.from_dict(action)


def _signature(action: Action) -> str:
    """Identity of an action for retry counting: tool plus normalized arguments."""
    return json.dumps([normalize_text(action.tool or action.type), normalize_arguments(action.arguments)], sort_keys=True, default=str)


class NecessityGate:
    def __init__(
        self,
        goal: str,
        current_state: str = "",
        evaluator: Evaluator | None = None,
        config: GateConfig | None = None,
    ) -> None:
        self.goal = goal
        self.current_state = current_state
        self.evaluator = evaluator or Evaluator()
        self.config = config or GateConfig()
        self.stats = GateStats()
        self._history: list[ActionRecord] = []
        self._uncertain_runs: Counter[str] = Counter()

    @property
    def history(self) -> tuple[ActionRecord, ...]:
        return tuple(self._history)

    def update_state(self, current_state: str) -> None:
        """Tell the gate what the agent now knows (e.g. 'files were modified externally')."""
        self.current_state = current_state

    def check(self, action: ActionLike) -> GateVerdict:
        """Decide whether to run ``action`` now. Counts it as proposed."""
        proposed = _as_action(action)
        context = ActionContext(goal=self.goal, proposed_action=proposed, current_state=self.current_state, history=self.history)
        decision = self.evaluator.evaluate(context)
        allow, why = self._apply_policy(proposed, decision)
        self.stats.proposed += 1
        if allow:
            self.stats.allowed += 1
            if decision.decision is Decision.UNCERTAIN:
                self._uncertain_runs[_signature(proposed)] += 1
        else:
            self.stats.skipped += 1
            self.stats.skipped_by_reason[why] += 1
        return GateVerdict(allow=allow, decision=decision, why=why)

    def _apply_policy(self, action: Action, decision: ActionDecision) -> tuple[bool, str]:
        if decision.decision is Decision.NECESSARY:
            return True, decision.reason_code.value
        if decision.decision is Decision.UNNECESSARY:
            return False, decision.reason_code.value
        if self.config.uncertain_policy == "skip":
            return False, "UNCERTAIN_SKIPPED_BY_POLICY"
        cap = self.config.max_uncertain_repeats
        if cap is not None and self._uncertain_runs[_signature(action)] >= cap:
            return False, "UNCERTAIN_RETRY_BUDGET_EXHAUSTED"
        return True, decision.reason_code.value

    def record(self, action: ActionLike, result: str) -> None:
        """Add an executed action and its result to the history the gate judges against."""
        self._history.append(ActionRecord(action=_as_action(action), result=str(result)))

    def run(self, action: ActionLike, execute: Callable[[Action], Any]) -> tuple[GateVerdict, Any]:
        """Check, and if allowed execute and record. Returns (verdict, result or None)."""
        verdict = self.check(action)
        if not verdict.allow:
            return verdict, None
        proposed = _as_action(action)
        result = execute(proposed)
        self.record(proposed, "" if result is None else str(result))
        return verdict, result
