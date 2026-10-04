"""Extract decision-relevant features from a full ``ActionContext``.

Features are facts ("an identical read exists and nothing changed since"), not
judgements. ``scoring.py`` decides how much each fact matters.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from suffiss.necessity import lexicon
from suffiss.necessity.models import Action, ActionContext, ActionRecord
from suffiss.necessity.rules import (
    ActionKind,
    ResultStatus,
    action_text,
    classify_action,
    classify_result,
    concepts_of,
    content_stems,
    is_broad_action,
    is_doc_path,
    is_mutating,
    is_test_run,
    knowledge_gaps,
    overlap_coefficient,
    state_reports_change,
    target_of,
    targets_related,
)
from suffiss.necessity.similarity import SimilarityProvider, tokenize

GoalScope = Literal["narrow", "neutral", "broad"]

_EXPLICIT_COMPLETION = re.compile(r"\b(task|goal|objective)\s+(is\s+)?(complete|completed|done|achieved|finished)\b", re.I)
_MULTI_CLAUSE = re.compile(r"\band\b|\bthen\b|[;,]", re.I)
_FILE_LIKE = re.compile(r"\w\.[a-z]{1,5}\b", re.I)
_IMPLICIT_COMPLETION = 0.9
_EXPLICIT_COMPLETION_PROB = 0.95


@dataclass(frozen=True)
class HistoryMatch:
    """The most recent history entry equivalent to the proposed action."""

    index: int
    similarity: float
    status: ResultStatus
    changed_since: bool
    after_target_mutation: bool
    repeat_count: int


@dataclass(frozen=True)
class Features:
    kind: ActionKind
    mutating: bool
    context_sufficient: bool
    relevance: float
    concepts_disjoint: bool
    match: HistoryMatch | None
    post_change_observation: bool
    verification_candidate: bool
    prerequisite: bool
    information_need: bool
    broad_action: bool
    goal_scope: GoalScope
    completion: float


@dataclass(frozen=True)
class _Prepared:
    """Per-context values computed once and shared by the feature functions."""

    context: ActionContext
    kind: ActionKind
    statuses: tuple[ResultStatus, ...]
    mutations: tuple[int, ...]
    goal_stems: frozenset[str]
    action_stems: frozenset[str]


def extract_features(context: ActionContext, similarity: SimilarityProvider, duplicate_threshold: float) -> Features:
    prep = _prepare(context)
    proposed = context.proposed_action
    match = _find_match(prep, similarity, duplicate_threshold)
    verify_from = _last_mutation(prep, strict=True)
    relevance, disjoint = _relevance(prep.goal_stems, prep.action_stems)
    return Features(
        kind=prep.kind,
        mutating=is_mutating(proposed, prep.kind),
        context_sufficient=bool(prep.goal_stems) and bool(prep.action_stems),
        relevance=relevance,
        concepts_disjoint=disjoint,
        match=match,
        post_change_observation=verify_from is not None and prep.kind is not ActionKind.EXECUTE,
        verification_candidate=verify_from is not None and (match is None or match.index < verify_from),
        prerequisite=_is_prerequisite(prep, match, verify_from),
        information_need=_has_information_need(prep, match),
        broad_action=is_broad_action(proposed),
        goal_scope=_goal_scope(context.goal, prep.goal_stems),
        completion=_completion_probability(prep),
    )


def _prepare(context: ActionContext) -> _Prepared:
    statuses = tuple(classify_result(record.result) for record in context.history)
    mutations = tuple(
        i
        for i, (record, status) in enumerate(zip(context.history, statuses))
        # A mutation that visibly failed did not change anything.
        if is_mutating(record.action) and status not in {ResultStatus.FAILURE, ResultStatus.TRANSIENT_FAILURE}
    )
    return _Prepared(
        context=context,
        kind=classify_action(context.proposed_action),
        statuses=statuses,
        mutations=mutations,
        goal_stems=frozenset(content_stems(context.goal)),
        action_stems=frozenset(content_stems(action_text(context.proposed_action))),
    )


def _affects(prep: _Prepared, mutation: Action, *, strict: bool) -> bool:
    """Could ``mutation`` change what the proposed action would observe?

    Non-strict mode assumes yes when targets are unknown (safe for unblocking
    repeats). Strict mode requires a known related target (used to claim that
    an observation is a *verification* of that change).
    """
    proposed = prep.context.proposed_action
    mutated, observed = target_of(mutation), target_of(proposed)
    if prep.kind is ActionKind.EXECUTE:
        if strict and not is_test_run(proposed):
            return False
        return not (mutated and is_doc_path(mutated))
    if mutated and observed:
        return targets_related(mutated, observed)
    return not strict


def _last_mutation(prep: _Prepared, *, strict: bool, before: int | None = None) -> int | None:
    history = prep.context.history
    candidates = [i for i in prep.mutations if (before is None or i < before) and _affects(prep, history[i].action, strict=strict)]
    return candidates[-1] if candidates else None


def _find_match(prep: _Prepared, similarity: SimilarityProvider, threshold: float) -> HistoryMatch | None:
    history = prep.context.history
    proposed = prep.context.proposed_action
    scores = [similarity.action_similarity(record.action, proposed) for record in history]
    matches = [i for i, score in enumerate(scores) if score >= threshold]
    if not matches:
        return None
    index = matches[-1]
    last_change = _last_mutation(prep, strict=False)
    changed = (last_change is not None and last_change > index) or state_reports_change(prep.context.current_state)
    since = -1 if last_change is None else last_change
    return HistoryMatch(
        index=index,
        similarity=scores[index],
        status=prep.statuses[index],
        changed_since=changed,
        after_target_mutation=_last_mutation(prep, strict=True, before=index) is not None,
        repeat_count=sum(1 for i in matches if i > since),
    )


def _relevance(goal: frozenset[str], action: frozenset[str]) -> tuple[float, bool]:
    token_score = overlap_coefficient(set(goal), set(action))
    goal_concepts, action_concepts = concepts_of(goal), concepts_of(action)
    concept_score = overlap_coefficient(goal_concepts, action_concepts)
    disjoint = bool(goal_concepts and action_concepts) and concept_score == 0.0 and token_score == 0.0
    return max(token_score, concept_score), disjoint


def _related(left: frozenset[str] | set[str], right: frozenset[str] | set[str]) -> bool:
    return bool(set(left) & set(right)) or bool(concepts_of(left) & concepts_of(right))


def _is_prerequisite(prep: _Prepared, match: HistoryMatch | None, verify_from: int | None) -> bool:
    wants_change = bool(set(tokenize(prep.context.goal)) & lexicon.CHANGE_VERBS)
    return (
        wants_change
        and prep.kind is ActionKind.READ
        and match is None
        and verify_from is None
        and _related(prep.goal_stems, prep.action_stems)
    )


def _has_information_need(prep: _Prepared, match: HistoryMatch | None) -> bool:
    if is_mutating(prep.context.proposed_action, prep.kind):
        return False
    if match is not None and not match.changed_since and match.status is not ResultStatus.PENDING:
        return False
    return any(_related(content_stems(gap), prep.action_stems) for gap in knowledge_gaps(prep.context.current_state))


def _goal_scope(goal: str, goal_stems: frozenset[str]) -> GoalScope:
    if set(tokenize(goal)) & lexicon.BROAD_GOAL_WORDS:
        return "broad"
    if _FILE_LIKE.search(goal) or len(goal_stems) <= 6:
        return "narrow"
    return "neutral"


def _completion_probability(prep: _Prepared) -> float:
    context = prep.context
    texts = [context.current_state, *(record.result for record in context.history)]
    if any(_EXPLICIT_COMPLETION.search(text) for text in texts):
        return _EXPLICIT_COMPLETION_PROB
    if any(classify_action(record.action) is ActionKind.FINISH for record in context.history):
        return _EXPLICIT_COMPLETION_PROB
    return _IMPLICIT_COMPLETION if _implicitly_completed(prep) else 0.0


def _implicitly_completed(prep: _Prepared) -> bool:
    """A single-clause goal like "Run unit tests" done by one successful action."""
    goal = prep.context.goal
    words = tokenize(goal)
    if not words or not prep.goal_stems or _MULTI_CLAUSE.search(goal):
        return False
    verb = words[0]
    if verb not in lexicon.EXECUTE_GOAL_VERBS and verb not in lexicon.WRITE_GOAL_VERBS:
        return False
    for index, record in enumerate(prep.context.history):
        if prep.statuses[index] is ResultStatus.SUCCESS and _completes(prep, verb, index, record):
            return True
    return False


def _completes(prep: _Prepared, verb: str, index: int, record: ActionRecord) -> bool:
    kind = classify_action(record.action)
    if verb in lexicon.EXECUTE_GOAL_VERBS:
        if kind is not ActionKind.EXECUTE:
            return False
        # A later code change invalidates an earlier successful run.
        if any(i > index and not _is_doc_mutation(prep.context.history[i]) for i in prep.mutations):
            return False
    elif not is_mutating(record.action, kind):
        return False
    return _goal_coverage(prep.goal_stems, frozenset(content_stems(action_text(record.action)))) >= 0.6


def _is_doc_mutation(record: ActionRecord) -> bool:
    target = target_of(record.action)
    return bool(target and is_doc_path(target))


def _goal_coverage(goal: frozenset[str], action: frozenset[str]) -> float:
    action_concepts = concepts_of(action)
    covered = [stem for stem in goal if stem in action or concepts_of({stem}) & action_concepts]
    return len(covered) / len(goal)
