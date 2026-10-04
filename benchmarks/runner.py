"""Run the gate over the labelled benchmark and report real metrics.

Usage (from the repository root):  python -m benchmarks.runner [dataset.jsonl]
"""

from __future__ import annotations

import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from benchmarks.metrics import LABELS, Metrics, compute_metrics, format_metrics
from suffiss.necessity import ActionContext, Evaluator

DEFAULT_DATASET = Path(__file__).with_name("dataset.jsonl")
_REQUIRED_FIELDS = ("id", "goal", "current_state", "history", "proposed_action", "expected", "category", "reason")


@dataclass(frozen=True)
class CaseResult:
    id: str
    category: str
    expected: str
    predicted: str
    reason_code: str
    confidence: float


def load_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        case = json.loads(line)
        missing = [name for name in _REQUIRED_FIELDS if name not in case]
        if missing:
            raise ValueError(f"{path}:{line_number}: missing fields {missing}")
        if case["expected"] not in LABELS:
            raise ValueError(f"{path}:{line_number}: invalid expected label {case['expected']!r}")
        cases.append(case)
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{path}: duplicate case ids")
    return cases


def run_cases(cases: Sequence[dict[str, Any]], evaluator: Evaluator | None = None) -> list[CaseResult]:
    evaluator = evaluator or Evaluator()
    results = []
    for case in cases:
        decision = evaluator.evaluate(ActionContext.from_dict(case))
        results.append(
            CaseResult(
                id=case["id"],
                category=case["category"],
                expected=case["expected"],
                predicted=decision.decision.value,
                reason_code=decision.reason_code.value,
                confidence=decision.confidence,
            )
        )
    return results


def summarize(results: Sequence[CaseResult]) -> Metrics:
    return compute_metrics([r.expected for r in results], [r.predicted for r in results])


def format_report(results: Sequence[CaseResult]) -> str:
    sections = [format_metrics(summarize(results)), "", "Accuracy by category:"]
    by_category: dict[str, list[CaseResult]] = defaultdict(list)
    for result in results:
        by_category[result.category].append(result)
    for category, items in sorted(by_category.items()):
        correct = sum(1 for r in items if r.expected == r.predicted)
        sections.append(f"  {category:<14} {correct}/{len(items)}")
    misses = [r for r in results if r.expected != r.predicted]
    sections += ["", f"Misclassified ({len(misses)}):"]
    for r in misses:
        sections.append(f"  {r.id:<16} expected={r.expected:<12} predicted={r.predicted:<12} {r.reason_code}")
    return "\n".join(sections)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    path = Path(args[0]) if args else DEFAULT_DATASET
    print(format_report(run_cases(load_cases(path))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
