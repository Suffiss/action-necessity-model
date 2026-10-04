"""Public entry point: ``evaluate_action(context) -> ActionDecision``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from suffiss.necessity.adapters.base import NecessityAdapter
from suffiss.necessity.features import extract_features
from suffiss.necessity.models import ActionContext, ActionDecision, Decision, ReasonCode
from suffiss.necessity.scoring import (
    ScoringWeights,
    Thresholds,
    aggregate,
    contributions,
    decide,
    signals,
    strongest_reason,
)
from suffiss.necessity.similarity import LexicalSimilarity, SimilarityProvider

EXPLANATIONS: dict[ReasonCode, str] = {
    ReasonCode.DIRECT_GOAL_DEPENDENCY: "The action directly serves the stated goal.",
    ReasonCode.NEW_INFORMATION_REQUIRED: "The action gathers information the agent does not have yet.",
    ReasonCode.PREREQUISITE_ACTION: "The goal changes this target, and it has not been inspected first.",
    ReasonCode.STATE_CHANGED: "The action repeats an earlier one, but relevant state changed since then.",
    ReasonCode.VERIFICATION_REQUIRED: "The action checks the result of a change that has not been verified yet.",
    ReasonCode.DUPLICATE_ACTION: "An equivalent action already ran and nothing relevant changed since.",
    ReasonCode.GOAL_ALREADY_COMPLETED: "The history indicates the goal is already achieved.",
    ReasonCode.NO_NEW_INFORMATION: "The action is unlikely to reveal anything new.",
    ReasonCode.SCOPE_TOO_BROAD: "The action covers far more than the narrow goal needs.",
    ReasonCode.REDUNDANT_VERIFICATION: "The change was already verified and nothing changed since.",
    ReasonCode.UNCHANGED_RETRY: "The action failed before and nothing that would change the outcome has changed.",
    ReasonCode.LOW_GOAL_RELEVANCE: "The action does not appear related to the stated goal.",
    ReasonCode.INSUFFICIENT_CONTEXT: "The goal or the proposed action is too vague to judge reliably.",
}


@dataclass(frozen=True)
class EvaluatorConfig:
    thresholds: Thresholds = field(default_factory=Thresholds)
    weights: ScoringWeights = field(default_factory=ScoringWeights)
    similarity: SimilarityProvider = field(default_factory=LexicalSimilarity)
    duplicate_threshold: float = 0.95
    adapter: NecessityAdapter | None = None


class Evaluator:
    def __init__(self, config: EvaluatorConfig | None = None) -> None:
        self.config = config or EvaluatorConfig()

    def evaluate(self, context: ActionContext | Mapping[str, Any]) -> ActionDecision:
        if not isinstance(context, ActionContext):
            context = ActionContext.from_dict(context)
        config = self.config
        features = extract_features(context, config.similarity, config.duplicate_threshold)
        items = contributions(features, config.weights)
        score = self._blend_with_adapter(context, aggregate(items))
        decision, confidence = decide(score, config.thresholds)
        reason = strongest_reason(items, decision)
        if not features.context_sufficient or reason is None:
            # Abstain rather than guess: a weak context must never block an action.
            decision, confidence, reason = Decision.UNCERTAIN, 0.5, ReasonCode.INSUFFICIENT_CONTEXT
        return ActionDecision(
            decision=decision,
            confidence=round(confidence, 4),
            reason_code=reason,
            explanation=f"{EXPLANATIONS[reason]} (necessity score {score:.2f})",
            signals=signals(features),
        )

    def _blend_with_adapter(self, context: ActionContext, rule_score: float) -> float:
        adapter = self.config.adapter
        if adapter is None:
            return rule_score
        assessment = adapter.assess(context)
        if assessment is None:
            return rule_score
        return (1.0 - assessment.weight) * rule_score + assessment.weight * assessment.necessity


_DEFAULT = Evaluator()


def evaluate_action(context: ActionContext | Mapping[str, Any]) -> ActionDecision:
    """Judge whether ``context.proposed_action`` is necessary, using default settings."""
    return _DEFAULT.evaluate(context)
