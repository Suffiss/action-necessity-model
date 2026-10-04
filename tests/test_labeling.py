import csv
import json
from pathlib import Path

import pytest

from benchmarks import labeling
from benchmarks.labeling import (
    export_sheet,
    gold_rows,
    import_sheet,
    load_cases,
    parse_label,
    render_history,
    validate_annotator,
)


def _case(case_id: str, context_id: str) -> dict:
    return {
        "id": case_id,
        "context_id": context_id,
        "category": "coding",
        "goal": "Fix typo in README",
        "current_state": "",
        "history": [{"action": {"type": "file_read", "tool": "read_file", "description": "Read README.md",
                                "arguments": {"path": "README.md"}}, "result": "# Projcet"}],  # fmt: skip
        "proposed_action": {"type": "file_read", "tool": "read_file", "description": "=cmd|calc", "arguments": {}},
    }


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    v1 = tmp_path / "v1"
    v1.mkdir()
    cases = [_case("c1-a", "c1"), _case("c1-b", "c1"), _case("c2-a", "c2")]
    (v1 / "cases.jsonl").write_text("\n".join(json.dumps(c) for c in cases), encoding="utf-8")
    monkeypatch.setattr(labeling, "V1_DIR", v1)
    monkeypatch.setattr(labeling, "CASES_PATH", v1 / "cases.jsonl")
    monkeypatch.setattr(labeling, "LABELS_DIR", v1 / "labels")
    monkeypatch.setattr(labeling, "ADJUDICATION_PATH", v1 / "adjudication.jsonl")
    return tmp_path


def _fill(sheet: Path, out: Path, labels: dict[str, str]) -> None:
    with sheet.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    for row in rows:
        row["label"] = labels.get(row["id"], "")
    with out.open("w", encoding="utf-8-sig", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=labeling.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("necessary", "necessary"), (" N ", "necessary"), ("u", "unnecessary"), ("?", "uncertain"), ("", None)],
)
def test_parse_label(raw: str, expected: str | None) -> None:
    assert parse_label(raw) == expected


def test_parse_label_rejects_unknown_values() -> None:
    with pytest.raises(ValueError):
        parse_label("maybe")


@pytest.mark.parametrize("name", ["../evil", "Alice", "", "a" * 40, "author"])
def test_annotator_names_are_restricted(name: str) -> None:
    with pytest.raises(ValueError):
        validate_annotator(name)


def test_render_history_is_readable() -> None:
    text = render_history(_case("x", "c")["history"])
    assert text.startswith("1. read_file: Read README.md")
    assert "-> # Projcet" in text
    assert render_history([]) == "(no previous actions)"


def test_exported_sheet_has_blank_labels_and_neutralises_formulas(workspace: Path) -> None:
    sheet = workspace / "sheet.csv"
    export_sheet(load_cases(), sheet)
    with sheet.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source))
    assert [r["id"] for r in rows] == ["c1-a", "c1-b", "c2-a"]
    assert all(r["label"] == "" for r in rows)
    assert not any(cell.startswith("=") for r in rows for cell in r.values())


def test_import_requires_complete_and_known_labels(workspace: Path) -> None:
    sheet, filled = workspace / "sheet.csv", workspace / "filled.csv"
    export_sheet(load_cases(), sheet)
    _fill(sheet, filled, {"c1-a": "n"})
    ids = [c["id"] for c in load_cases()]
    with pytest.raises(ValueError):
        import_sheet(filled, ids)
    assert import_sheet(filled, ids, allow_partial=True) == [{"id": "c1-a", "label": "necessary", "note": ""}]
    with pytest.raises(ValueError):
        import_sheet(filled, ["c2-a"])


def test_full_workflow_produces_grouped_gold_split(workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    sheet = workspace / "sheet.csv"
    assert labeling.main(["export", "--out", str(sheet)]) == 0
    for name, labels in {"ann": {"c1-a": "n", "c1-b": "u", "c2-a": "?"}, "bob": {"c1-a": "n", "c1-b": "n", "c2-a": "?"}}.items():
        filled = workspace / f"{name}.csv"
        _fill(sheet, filled, labels)
        assert labeling.main(["import", str(filled), "--annotator", name]) == 0
    assert labeling.main(["agree"]) == 0
    assert labeling.main(["gold", "--test-fraction", "1.0"]) == 0
    v1 = labeling.V1_DIR
    test_rows = [json.loads(line) for line in (v1 / "gold-test.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["id"]: r["expected"] for r in test_rows} == {"c1-a": "necessary", "c2-a": "uncertain"}
    assert "disputed (need adjudication): 1" in capsys.readouterr().out


def test_pilot_export_and_import_of_a_subset(workspace: Path) -> None:
    pilot_list = workspace / "pilot.txt"
    pilot_list.write_text("# pilot\nc2\n", encoding="utf-8")
    sheet, filled = workspace / "pilot.csv", workspace / "pilot-filled.csv"
    assert labeling.main(["export", "--out", str(sheet), "--contexts", str(pilot_list)]) == 0
    _fill(sheet, filled, {"c2-a": "u"})
    rows = import_sheet(filled, [c["id"] for c in load_cases()])
    assert rows == [{"id": "c2-a", "label": "unnecessary", "note": ""}]


def test_unknown_pilot_context_is_rejected(workspace: Path) -> None:
    with pytest.raises(ValueError):
        labeling.select_contexts(load_cases(), ["nope"])


def _web_doc(**overrides: object) -> dict:
    body = {"annotator": "lin", "set": "pilot", "labels": {"c1-a": {"label": "necessary", "note": " ok "},
            "c1-b": {"label": "", "note": ""}}, "benchmark": "v1"}  # fmt: skip
    body.update(overrides)
    return body


def test_import_web_document_accepts_page_body_and_db_record() -> None:
    for document in (_web_doc(), {"id": "u_x", "data": _web_doc(), "version": 3}):
        annotator, task_set, rows = labeling.import_web_document(document, ["c1-a", "c1-b"])
        assert (annotator, task_set) == ("lin", "pilot")
        assert rows == [{"id": "c1-a", "label": "necessary", "note": "ok"}]


@pytest.mark.parametrize(
    "document",
    [
        _web_doc(annotator="../x"),
        _web_doc(annotator="author"),
        _web_doc(labels={"zzz": {"label": "necessary"}}),
        _web_doc(labels={"c1-a": {"label": "maybe"}}),
        _web_doc(labels={"c1-a": "necessary"}),
        {"unrelated": True},
    ],
)
def test_import_web_document_rejects_untrusted_input(document: dict) -> None:
    with pytest.raises(ValueError):
        labeling.import_web_document(document, ["c1-a", "c1-b"])


def test_import_web_command_writes_annotator_labels(workspace: Path) -> None:
    source = workspace / "lin.json"
    source.write_text(json.dumps({"data": _web_doc(labels={"c2-a": {"label": "uncertain", "note": ""}})}), encoding="utf-8")
    assert labeling.main(["import-web", str(source)]) == 0
    assert labeling.load_annotations() == {"lin": {"c2-a": "uncertain"}}


def test_author_labels_are_excluded_from_gold(workspace: Path) -> None:
    labels_dir = labeling.LABELS_DIR
    labels_dir.mkdir()
    (labels_dir / "author.jsonl").write_text('{"id": "c1-a", "label": "unnecessary"}', encoding="utf-8")
    assert "author" not in labeling.load_annotations()
    assert "author" in labeling.load_annotations(include_author=True)


def test_gold_rows_use_runner_format() -> None:
    rows = gold_rows([_case("c1-a", "c1")], {"c1-a": "necessary"}, ["ann", "bob"])
    assert rows[0]["expected"] == "necessary"
    assert "ann, bob" in rows[0]["reason"]


def test_commands_report_errors_without_traceback(workspace: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert labeling.main(["agree"]) == 2
    assert capsys.readouterr().err.startswith("error:")
