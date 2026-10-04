"""Interface for optional model-backed scorers.

No adapter ships with v0 and none is required. A future adapter (a local
classifier, an embedding model, or a remote model) implements
``NecessityAdapter`` and is passed via ``EvaluatorConfig.adapter``; the
evaluator blends its opinion with the rule-based score.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from suffiss.necessity.models import ActionContext


@dataclass(frozen=True)
class AdapterAssessment:
    """An adapter's view of how necessary the proposed action is."""

    necessity: float
    weight: float = 0.5

    def __post_init__(self) -> None:
        for name, value in (("necessity", self.necessity), ("weight", self.weight)):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be within [0, 1], got {value}")


class NecessityAdapter(Protocol):
    name: str

    def assess(self, context: ActionContext) -> AdapterAssessment | None:
        """Return an assessment, or None to abstain and defer to the rules."""
        ...
