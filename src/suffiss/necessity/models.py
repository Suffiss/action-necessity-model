"""Typed data models for the action necessity gate.

All models are immutable dataclasses with explicit ``from_dict`` / ``to_dict``
conversion so the JSON interface stays stable and untrusted input is validated
at the boundary rather than deep inside the evaluator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Mapping


class ContextValidationError(ValueError):
    """Raised when an input context does not match the documented schema."""


class Decision(StrEnum):
    NECESSARY = "necessary"
    UNNECESSARY = "unnecessary"
    UNCERTAIN = "uncertain"


class ReasonCode(StrEnum):
    # Reasons that support executing the action.
    DIRECT_GOAL_DEPENDENCY = "DIRECT_GOAL_DEPENDENCY"
    NEW_INFORMATION_REQUIRED = "NEW_INFORMATION_REQUIRED"
    PREREQUISITE_ACTION = "PREREQUISITE_ACTION"
    STATE_CHANGED = "STATE_CHANGED"
    VERIFICATION_REQUIRED = "VERIFICATION_REQUIRED"
    # Reasons that support skipping the action.
    DUPLICATE_ACTION = "DUPLICATE_ACTION"
    GOAL_ALREADY_COMPLETED = "GOAL_ALREADY_COMPLETED"
    NO_NEW_INFORMATION = "NO_NEW_INFORMATION"
    SCOPE_TOO_BROAD = "SCOPE_TOO_BROAD"
    REDUNDANT_VERIFICATION = "REDUNDANT_VERIFICATION"
    UNCHANGED_RETRY = "UNCHANGED_RETRY"
    LOW_GOAL_RELEVANCE = "LOW_GOAL_RELEVANCE"
    # Reason for abstaining.
    INSUFFICIENT_CONTEXT = "INSUFFICIENT_CONTEXT"


def _require_str(data: Mapping[str, Any], key: str, *, default: str | None = None) -> str:
    value = data.get(key, default)
    if value is None:
        raise ContextValidationError(f"missing required field '{key}'")
    if not isinstance(value, str):
        raise ContextValidationError(f"field '{key}' must be a string, got {type(value).__name__}")
    return value


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContextValidationError(f"'{name}' must be an object, got {type(value).__name__}")
    return value


def _validate_arguments(value: Any) -> dict[str, Any]:
    arguments = _require_mapping({} if value is None else value, "arguments")
    for key in arguments:
        if not isinstance(key, str):
            raise ContextValidationError("argument names must be strings")
    return dict(arguments)


@dataclass(frozen=True)
class Action:
    """A single agent action, either already taken or proposed."""

    type: str
    tool: str = ""
    description: str = ""
    arguments: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Any) -> Action:
        data = _require_mapping(data, "action")
        return cls(
            type=_require_str(data, "type", default=""),
            tool=_require_str(data, "tool", default=""),
            description=_require_str(data, "description", default=""),
            arguments=_validate_arguments(data.get("arguments")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "tool": self.tool,
            "description": self.description,
            "arguments": dict(self.arguments),
        }


@dataclass(frozen=True)
class ActionRecord:
    """An action from the agent's history together with its observed result."""

    action: Action
    result: str = ""

    @classmethod
    def from_dict(cls, data: Any) -> ActionRecord:
        data = _require_mapping(data, "history item")
        if "action" not in data:
            raise ContextValidationError("history item is missing 'action'")
        return cls(action=Action.from_dict(data["action"]), result=_require_str(data, "result", default=""))

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action.to_dict(), "result": self.result}


@dataclass(frozen=True)
class ActionContext:
    """Everything the gate sees when judging a proposed action."""

    goal: str
    proposed_action: Action
    current_state: str = ""
    history: tuple[ActionRecord, ...] = ()

    @classmethod
    def from_dict(cls, data: Any) -> ActionContext:
        data = _require_mapping(data, "context")
        if "proposed_action" not in data:
            raise ContextValidationError("missing required field 'proposed_action'")
        raw_history = data.get("history") or []
        if not isinstance(raw_history, list):
            raise ContextValidationError("'history' must be a list")
        return cls(
            goal=_require_str(data, "goal", default=""),
            current_state=_require_str(data, "current_state", default=""),
            history=tuple(ActionRecord.from_dict(item) for item in raw_history),
            proposed_action=Action.from_dict(data["proposed_action"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "current_state": self.current_state,
            "history": [record.to_dict() for record in self.history],
            "proposed_action": self.proposed_action.to_dict(),
        }


def _check_unit_interval(name: str, value: float) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"signal '{name}' must be within [0, 1], got {value}")


@dataclass(frozen=True)
class SignalScores:
    """Public, interpretable signals behind a decision. All values lie in [0, 1]."""

    goal_relevance: float = 0.0
    new_information_gain: float = 0.0
    duplicate_action_probability: float = 0.0
    task_completion_probability: float = 0.0
    scope_alignment: float = 1.0

    def __post_init__(self) -> None:
        for name, value in self.to_dict().items():
            _check_unit_interval(name, value)

    def to_dict(self) -> dict[str, float]:
        return {
            "goal_relevance": self.goal_relevance,
            "new_information_gain": self.new_information_gain,
            "duplicate_action_probability": self.duplicate_action_probability,
            "task_completion_probability": self.task_completion_probability,
            "scope_alignment": self.scope_alignment,
        }


@dataclass(frozen=True)
class ActionDecision:
    """The gate's verdict on a proposed action."""

    decision: Decision
    confidence: float
    reason_code: ReasonCode
    explanation: str
    signals: SignalScores = field(default_factory=SignalScores)

    def __post_init__(self) -> None:
        _check_unit_interval("confidence", self.confidence)

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "confidence": round(self.confidence, 4),
            "reason_code": self.reason_code.value,
            "explanation": self.explanation,
            "signals": {name: round(value, 4) for name, value in self.signals.to_dict().items()},
        }
