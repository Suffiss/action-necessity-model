import json
import re
from pathlib import Path

import pytest

from benchmarks.labeler.build import PLACEHOLDER, TEMPLATE, build, group_scenarios, page_data
from benchmarks.labeling import LABELS_DIR, import_sheet, load_cases


@pytest.fixture(scope="module")
def pages(tmp_path_factory: pytest.TempPathFactory) -> dict[str, str]:
    dist = tmp_path_factory.mktemp("dist")
    return {path.name: path.read_text(encoding="utf-8") for path in build(dist)}


def _embedded(html: str) -> dict:
    match = re.search(r'<script id="data" type="application/json">(.*?)</script>', html, re.S)
    assert match, "data script missing"
    return json.loads(match.group(1))


def test_template_has_exactly_one_placeholder() -> None:
    assert TEMPLATE.read_text(encoding="utf-8").count(PLACEHOLDER) == 1


def test_scenarios_group_five_candidates_each() -> None:
    scenarios = group_scenarios(load_cases())
    assert len(scenarios) == 60
    assert {len(s["candidates"]) for s in scenarios} == {5}


def test_grouping_rejects_inconsistent_scenarios() -> None:
    cases = load_cases()[:2]
    broken = [cases[0], {**cases[1], "goal": "something else"}]
    with pytest.raises(ValueError):
        group_scenarios(broken)


def test_embedded_json_cannot_close_the_script_tag() -> None:
    case = {**load_cases()[0], "goal": "evil </script><script>alert(1)</script>"}
    text = page_data([case], [])
    assert "</script" not in text
    assert json.loads(text)["scenarios"][0]["goal"].startswith("evil </script>")


def test_both_variants_embed_all_cases(pages: dict[str, str]) -> None:
    for html in pages.values():
        data = _embedded(html)
        assert sum(len(s["candidates"]) for s in data["scenarios"]) == 300
        assert len(data["pilot"]) == 6


def test_standalone_variant_is_a_full_document(pages: dict[str, str]) -> None:
    assert pages["index.html"].startswith("<!doctype html>")
    assert 'name="viewport"' in pages["index.html"]
    assert not pages["labeler.html"].lstrip().startswith("<!doctype")


def test_pages_never_contain_author_labels(pages: dict[str, str]) -> None:
    notes = [json.loads(line)["note"] for line in (LABELS_DIR / "author.jsonl").read_text(encoding="utf-8").splitlines()]
    for html in pages.values():
        leaked = [note for note in notes if note and note in html]
        assert not leaked, f"author notes leaked into the page: {leaked[:3]}"
        candidates = [c for s in _embedded(html)["scenarios"] for c in s["candidates"]]
        assert all(set(c) == {"id", "action"} for c in candidates)


def test_page_csv_export_format_imports_cleanly(tmp_path: Path) -> None:
    # Mirrors buildCsv() in the template: BOM, id/category/label/note, empty label for unlabelled rows.
    ids = [case["id"] for case in load_cases()]
    sheet = tmp_path / "labels-lin-pilot.csv"
    sheet.write_text("﻿id,category,label,note\n" + f"{ids[0]},coding,necessary,\n{ids[1]},coding,,\n", encoding="utf-8")
    assert import_sheet(sheet, ids, allow_partial=True) == [{"id": ids[0], "label": "necessary", "note": ""}]
    with pytest.raises(ValueError):
        import_sheet(sheet, ids)
