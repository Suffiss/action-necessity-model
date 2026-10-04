import json
from pathlib import Path

import pytest

from benchmarks.runner import DEFAULT_DATASET, format_report, load_cases, run_cases


def test_shipped_dataset_is_valid_and_balanced_across_categories() -> None:
    cases = load_cases(DEFAULT_DATASET)
    assert len(cases) >= 30
    categories = {case["category"] for case in cases}
    assert categories >= {"coding", "research", "browser", "database", "filesystem", "tool_calling"}
    assert {case["expected"] for case in cases} == {"necessary", "unnecessary", "uncertain"}


def test_runner_evaluates_every_case() -> None:
    cases = load_cases(DEFAULT_DATASET)
    results = run_cases(cases)
    assert [r.id for r in results] == [case["id"] for case in cases]
    report = format_report(results)
    assert "False unnecessary rate" in report
    assert "Accuracy by category" in report


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "cases.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    return path


def _row(**overrides: object) -> dict:
    row = {
        "id": "x-1",
        "goal": "g",
        "current_state": "",
        "history": [],
        "proposed_action": {"type": "search"},
        "expected": "necessary",
        "category": "coding",
        "reason": "r",
    }
    row.update(overrides)
    return row


@pytest.mark.parametrize(
    "rows",
    [
        [{k: v for k, v in _row().items() if k != "reason"}],
        [_row(expected="maybe")],
        [_row(), _row()],
    ],
)
def test_invalid_datasets_are_rejected(tmp_path: Path, rows: list[dict]) -> None:
    with pytest.raises(ValueError):
        load_cases(_write(tmp_path, rows))
