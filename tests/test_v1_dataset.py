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


def _plain_zh() -> dict[str, dict]:
    rows = [json.loads(line) for line in (V1_DIR / "plain_zh.jsonl").read_text(encoding="utf-8").splitlines()]
    return {row["context_id"]: row for row in rows}


def test_plain_chinese_covers_every_scenario_step_and_candidate() -> None:
    plain = _plain_zh()
    cases = load_cases(CASES_PATH)
    assert set(plain) == {case["context_id"] for case in cases}
    for case in cases:
        row = plain[case["context_id"]]
        assert row["candidates"].get(case["id"]), case["id"]
        assert len(row["history"]) == len(case["history"]), case["context_id"]
        assert bool(row["state"]) == bool(case["current_state"]), case["context_id"]


def test_plain_chinese_candidates_do_not_hint_at_answers() -> None:
    # Descriptions say what an action does; judging it is the annotator's job.
    hints = ("多余", "不必要", "没必要", "又一次", "再次", "同样的", "重复执行")
    flagged = [(cid, text) for row in _plain_zh().values() for cid, text in row["candidates"].items() if any(h in text for h in hints)]
    assert not flagged


def test_pilot_scenarios_are_one_per_category_and_outside_the_test_split() -> None:
    lines = (V1_DIR / "pilot.txt").read_text(encoding="utf-8").splitlines()
    pilot = [line.strip() for line in lines if line.strip() and not line.startswith("#")]
    categories = {case["category"] for case in load_cases(CASES_PATH) if case["context_id"] in pilot}
    assert len(pilot) == 6 and categories == CATEGORIES
    assert not any(in_test_split(context_id, 0.6) for context_id in pilot)
