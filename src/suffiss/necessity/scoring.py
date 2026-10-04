"""Turn extracted features into an interpretable necessity score.

score = 0.5 + sum(positive contributions) - sum(penalties), clamped to [0, 1].

Each contribution carries the reason code that explains it, so the final
reason is simply the strongest contribution pointing the same way as the
decision. Weights are round numbers chosen from the design rationale in the
comments, not fitted to benchmark cases.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from suffiss.necessity.features import Features
from suffiss.necessity.models import Decision, ReasonCode, SignalScores
from suffiss.necessity.rules import ActionKind, ResultStatus

NEUTRAL_SCORE = 0.5
_MIN_RELEVANCE = 0.3
_WEAK_RELEVANCE = 0.1


@dataclass(frozen=True)
class Thresholds:
    necessary: float = 0.65
    unnecessary: float = 0.35

    def __post_init__(self) -> None:
        if not 0.0 <= self.unnecessary < self.necessary <= 1.0:
            raise ValueError("thresholds must satisfy 0 <= unnecessary < necessary <= 1")


@dataclass(frozen=True)
class ScoringWeights:
    # Support for executing the action.
    goal_relevance: float = 0.15
    novelty: float = 0.10
    information_need: float = 0.25
    prerequisite: float = 0.30
    state_change: float = 0.35  # must offset most of `duplicate`: changed state makes repeats legitimate
    verification: float = 0.30
    polling: float = 0.20
    continuation: float = 0.25  # paging through output the agent already chose to read
    follow_up: float = 0.25  # acting on a lead an earlier result surfaced
    finish: float = 0.30
    # Penalties. A lone exact duplicate (0.5) is enough to block; most other
    # single penalties only push into "uncertain" unless corroborated.
    duplicate: float = 0.50
    deterministic_retry: float = 0.50
    transient_retry: float = 0.15  # per repeated attempt: transient errors may clear on retry
    completion: float = 0.40
    scope_narrow_goal: float = 0.40
    scope_neutral_goal: float = 0.15
    unrelated: float = 0.35
    weak_relevance: float = 0.10


@dataclass(frozen=True)
class Contribution:
    reason: ReasonCode
    value: float


def contributions(features: Features, weights: ScoringWeights) -> list[Contribution]:
    if features.kind is ActionKind.FINISH:
        # Finishing never costs a tool call; only argue for it once the goal looks done.
        done = features.completion >= 0.5
        return [Contribution(ReasonCode.DIRECT_GOAL_DEPENDENCY, weights.finish if done else 0.0)]
    items = _support(features, weights) + _penalties(features, weights)
    return [item for item in items if item.value != 0.0]


def _support(f: Features, w: ScoringWeights) -> list[Contribution]:
    items: list[Contribution] = []
    if f.relevance >= _MIN_RELEVANCE:
        items.append(Contribution(ReasonCode.DIRECT_GOAL_DEPENDENCY, w.goal_relevance * f.relevance))
        if f.match is None:
            novel_reason = ReasonCode.DIRECT_GOAL_DEPENDENCY if f.mutating else ReasonCode.NEW_INFORMATION_REQUIRED
            items.append(Contribution(novel_reason, w.novelty))
    if f.information_need:
        items.append(Contribution(ReasonCode.NEW_INFORMATION_REQUIRED, w.information_need))
    if f.continuation:
        items.append(Contribution(ReasonCode.NEW_INFORMATION_REQUIRED, w.continuation))
    if f.follow_up:
        # Reading a surfaced lead gathers information; writing to it acts on the
        # agent's own findings, which ties it to the goal.
        reason = ReasonCode.DIRECT_GOAL_DEPENDENCY if f.mutating else ReasonCode.NEW_INFORMATION_REQUIRED
        items.append(Contribution(reason, w.follow_up))
    if f.prerequisite:
        items.append(Contribution(ReasonCode.PREREQUISITE_ACTION, w.prerequisite))
    if f.match is not None and f.match.changed_since:
        reason = ReasonCode.VERIFICATION_REQUIRED if f.post_change_observation else ReasonCode.STATE_CHANGED
        items.append(Contribution(reason, w.state_change))
    elif f.verification_candidate:
        items.append(Contribution(ReasonCode.VERIFICATION_REQUIRED, w.verification))
    if f.match is not None and not f.match.changed_since and f.match.status is ResultStatus.PENDING:
        items.append(Contribution(ReasonCode.NEW_INFORMATION_REQUIRED, w.polling))
    return items


def _penalties(f: Features, w: ScoringWeights) -> list[Contribution]:
    items = _repeat_penalties(f, w)
    exempt_from_completion = f.verification_candidate or (f.match is not None and f.match.changed_since)
    if f.completion > 0.0 and not exempt_from_completion:
        items.append(Contribution(ReasonCode.GOAL_ALREADY_COMPLETED, -w.completion * f.completion))
    if f.broad_action and f.goal_scope != "broad":
        penalty = w.scope_narrow_goal if f.goal_scope == "narrow" else w.scope_neutral_goal
        items.append(Contribution(ReasonCode.SCOPE_TOO_BROAD, -penalty))
    # Verifying a change, continuing truncated output, or following a lead
    # inherits relevance from the earlier step, even without shared words.
    if f.verification_candidate or f.continuation or f.follow_up:
        return items
    if f.concepts_disjoint:
        items.append(Contribution(ReasonCode.LOW_GOAL_RELEVANCE, -w.unrelated))
    elif f.relevance < _WEAK_RELEVANCE:
        items.append(Contribution(ReasonCode.LOW_GOAL_RELEVANCE, -w.weak_relevance))
    return items


def _repeat_penalties(f: Features, w: ScoringWeights) -> list[Contribution]:
    match = f.match
    if match is None or match.changed_since:
        return []
    if match.status is ResultStatus.FAILURE:
        return [Contribution(ReasonCode.UNCHANGED_RETRY, -w.deterministic_retry)]
    if match.status is ResultStatus.TRANSIENT_FAILURE:
        return [Contribution(ReasonCode.UNCHANGED_RETRY, -w.transient_retry * min(match.repeat_count, 3))]
    if match.status is ResultStatus.PENDING:
        return []
    # A write identified only by its file (edit_file(path)) usually carries its
    # real payload elsewhere, so matching arguments are weak evidence of a
    # repeat. Writes whose arguments include the payload get the full penalty.
    scale = 0.5 if f.mutating and not f.payload_visible else 1.0
    reason = ReasonCode.REDUNDANT_VERIFICATION if match.after_target_mutation else ReasonCode.DUPLICATE_ACTION
    return [Contribution(reason, -w.duplicate * match.similarity * scale)]


def aggregate(items: list[Contribution]) -> float:
    return min(1.0, max(0.0, NEUTRAL_SCORE + sum(item.value for item in items)))


def strongest_reason(items: list[Contribution], decision: Decision) -> ReasonCode | None:
    totals: dict[ReasonCode, float] = defaultdict(float)
    for item in items:
        totals[item.reason] += item.value
    if decision is Decision.NECESSARY:
        candidates = {code: value for code, value in totals.items() if value > 0}
    elif decision is Decision.UNNECESSARY:
        candidates = {code: -value for code, value in totals.items() if value < 0}
    else:
        # Ties favour the penalty: it explains why the action was not cleared.
        candidates = {code: abs(value) + (1e-9 if value < 0 else 0.0) for code, value in totals.items()}
    return max(candidates, key=candidates.__getitem__) if candidates else None


def decide(score: float, thresholds: Thresholds) -> tuple[Decision, float]:
    """Decision plus a confidence that grows with distance past the threshold."""
    if score >= thresholds.necessary:
        span = max(1.0 - thresholds.necessary, 1e-9)
        return Decision.NECESSARY, 0.5 + 0.5 * min(1.0, (score - thresholds.necessary) / span)
    if score <= thresholds.unnecessary:
        span = max(thresholds.unnecessary, 1e-9)
        return Decision.UNNECESSARY, 0.5 + 0.5 * min(1.0, (thresholds.unnecessary - score) / span)
    middle = (thresholds.necessary + thresholds.unnecessary) / 2
    half_band = (thresholds.necessary - thresholds.unnecessary) / 2
    return Decision.UNCERTAIN, 0.5 * (1.0 - abs(score - middle) / half_band) + 0.25


def signals(features: Features) -> SignalScores:
    match = features.match
    unchanged_repeat = match is not None and not match.changed_since and match.status is not ResultStatus.PENDING
    if unchanged_repeat:
        duplicate, information = match.similarity, 1.0 - match.similarity
    else:
        duplicate = 0.2 * match.similarity if match is not None else 0.0
        information = 0.2 + 0.4 * features.relevance + (0.4 if features.information_need else 0.0)
        if match is not None or features.verification_candidate:
            information = max(information, 0.8)
    scope = 1.0
    if features.broad_action and features.goal_scope != "broad":
        scope = 0.2 if features.goal_scope == "narrow" else 0.6
    return SignalScores(
        goal_relevance=round(features.relevance, 4),
        new_information_gain=round(min(1.0, information), 4),
        duplicate_action_probability=round(duplicate, 4),
        task_completion_probability=round(features.completion, 4),
        scope_alignment=scope,
    )
