"""Action Necessity Model: decide whether an agent's proposed next action is necessary."""

from suffiss.necessity.evaluator import Evaluator, EvaluatorConfig, Explanation, evaluate_action, explain_action
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
from suffiss.necessity.scoring import ScoringWeights, Thresholds

__all__ = [
    "Action",
    "ActionContext",
    "ActionDecision",
    "ActionRecord",
    "ContextValidationError",
    "Decision",
    "Evaluator",
    "EvaluatorConfig",
    "Explanation",
    "ReasonCode",
    "ScoringWeights",
    "SignalScores",
    "Thresholds",
    "evaluate_action",
    "explain_action",
]
