"""Classification and safety metrics for the necessity benchmark.

The headline safety metric is ``false_unnecessary_rate``: the share of truly
necessary actions the gate would have blocked. Undefined ratios (empty
denominators) are reported as 0.0.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

LABELS = ("necessary", "unnecessary", "uncertain")


@dataclass(frozen=True)
class ClassMetrics:
    precision: float
    recall: float
    f1: float
    support: int


@dataclass(frozen=True)
class Metrics:
    cases: int
    accuracy: float
    per_class: dict[str, ClassMetrics]
    confusion: dict[str, dict[str, int]]  # expected label -> predicted label -> count
    false_unnecessary_rate: float  # necessary actions predicted unnecessary
    unnecessary_action_detection_rate: float  # unnecessary actions predicted unnecessary
    potential_action_reduction_rate: float  # all actions the gate would skip
    uncertain_rate: float  # all actions the gate abstained on


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def confusion_matrix(expected: Sequence[str], predicted: Sequence[str]) -> dict[str, dict[str, int]]:
    if len(expected) != len(predicted):
        raise ValueError("expected and predicted must have the same length")
    matrix = {truth: {guess: 0 for guess in LABELS} for truth in LABELS}
    for truth, guess in zip(expected, predicted):
        if truth not in LABELS or guess not in LABELS:
            raise ValueError(f"unknown label pair: {truth!r}, {guess!r}")
        matrix[truth][guess] += 1
    return matrix


def _class_metrics(matrix: dict[str, dict[str, int]], label: str) -> ClassMetrics:
    true_positive = matrix[label][label]
    predicted = sum(matrix[truth][label] for truth in LABELS)
    support = sum(matrix[label].values())
    precision = _ratio(true_positive, predicted)
    recall = _ratio(true_positive, support)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return ClassMetrics(precision=precision, recall=recall, f1=f1, support=support)


def compute_metrics(expected: Sequence[str], predicted: Sequence[str]) -> Metrics:
    matrix = confusion_matrix(expected, predicted)
    total = len(expected)
    predicted_counts = {label: sum(matrix[truth][label] for truth in LABELS) for label in LABELS}
    return Metrics(
        cases=total,
        accuracy=_ratio(sum(matrix[label][label] for label in LABELS), total),
        per_class={label: _class_metrics(matrix, label) for label in LABELS},
        confusion=matrix,
        false_unnecessary_rate=_ratio(matrix["necessary"]["unnecessary"], sum(matrix["necessary"].values())),
        unnecessary_action_detection_rate=_ratio(matrix["unnecessary"]["unnecessary"], sum(matrix["unnecessary"].values())),
        potential_action_reduction_rate=_ratio(predicted_counts["unnecessary"], total),
        uncertain_rate=_ratio(predicted_counts["uncertain"], total),
    )


def format_metrics(metrics: Metrics) -> str:
    lines = [
        f"Cases: {metrics.cases}",
        f"Accuracy: {metrics.accuracy:.2f}",
        "",
        f"{'label':<12} {'precision':>9} {'recall':>7} {'f1':>5} {'support':>8}",
    ]
    for label, scores in metrics.per_class.items():
        lines.append(f"{label:<12} {scores.precision:>9.2f} {scores.recall:>7.2f} {scores.f1:>5.2f} {scores.support:>8}")
    lines += [
        "",
        f"False unnecessary rate:            {metrics.false_unnecessary_rate:.1%}",
        f"Unnecessary action detection rate: {metrics.unnecessary_action_detection_rate:.1%}",
        f"Potential action reduction rate:   {metrics.potential_action_reduction_rate:.1%}",
        f"Uncertain rate:                    {metrics.uncertain_rate:.1%}",
        "",
        "Confusion matrix (rows = expected, columns = predicted):",
        f"{'':<12} " + " ".join(f"{label:>11}" for label in LABELS),
    ]
    for truth in LABELS:
        lines.append(f"{truth:<12} " + " ".join(f"{metrics.confusion[truth][guess]:>11}" for guess in LABELS))
    return "\n".join(lines)
