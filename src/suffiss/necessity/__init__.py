"""Action Necessity Model: decide whether an agent's proposed next action is necessary."""

from suffiss.necessity.evaluator import Evaluator, EvaluatorConfig, Explanation, evaluate_action, explain_action
from suffiss.necessity.gate import GateConfig, GateStats, GateVerdict, NecessityGate
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
    "GateConfig",
    "GateStats",
    "GateVerdict",
    "NecessityGate",
    "ReasonCode",
    "ScoringWeights",
    "SignalScores",
    "Thresholds",
    "evaluate_action",
    "explain_action",
]
