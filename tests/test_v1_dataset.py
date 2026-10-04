import json
from collections import Counter

from benchmarks.agreement import in_test_split
from benchmarks.labeling import CASES_PATH, LABELS_DIR, V1_DIR, load_cases

CATEGORIES = {"coding", "research", "browser", "database", "filesystem", "tool_calling"}


def test_v1_has_five_candidates_for_each_of_sixty_scenarios() -> None:
    cases = load_cases(CASES_PATH)
    per_context = Counter(case["context_id"] for case in cases)
    assert len(cases) == 300
    assert len(per_context) == 60
    assert set(per_context.values()) == {5}
    assert {case["category"] for case in cases} == CATEGORIES


def test_v1_cases_carry_no_labels() -> None:
    assert not any("expected" in case or "label" in case for case in load_cases(CASES_PATH))


def test_author_labels_cover_every_case() -> None:
    rows = [json.loads(line) for line in (LABELS_DIR / "author.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {row["id"] for row in rows} == {case["id"] for case in load_cases(CASES_PATH)}
    assert {row["label"] for row in rows} == {"necessary", "unnecessary", "uncertain"}


def test_pilot_scenarios_are_one_per_category_and_outside_the_test_split() -> None:
    lines = (V1_DIR / "pilot.txt").read_text(encoding="utf-8").splitlines()
    pilot = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    categories = {case["category"] for case in load_cases(CASES_PATH) if case["context_id"] in pilot}
    assert len(pilot) == 6 and categories == CATEGORIES
    assert not any(in_test_split(context_id, 0.6) for context_id in pilot)
