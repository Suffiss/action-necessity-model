"""Labeling workflow for the v1 benchmark: export sheets, import labels, agree, build gold.

Usage (from the repository root):
    python -m benchmarks.labeling export --out sheet.csv
    python -m benchmarks.labeling import filled.csv --annotator alice
    python -m benchmarks.labeling import-web doc.json [--annotator alice]
    python -m benchmarks.labeling import-code code.txt --annotator alice
    python -m benchmarks.labeling agree
    python -m benchmarks.labeling gold [--test-fraction 0.6]

See docs/labeling-guide.md for how to label.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from benchmarks import answer_code
from benchmarks.agreement import all_pairs, build_gold, format_pairs, in_test_split
from suffiss.necessity import ActionContext

V1_DIR = Path(__file__).with_name("v1")
CASES_PATH = V1_DIR / "cases.jsonl"
LABELS_DIR = V1_DIR / "labels"
ADJUDICATION_PATH = V1_DIR / "adjudication.jsonl"
PILOT_PATH = V1_DIR / "pilot.txt"
BACKGROUND_FILE = "annotators.json"  # lives in LABELS_DIR; .json so it is never read as labels
SKIP = "skip"  # "I don't understand this case": answered, but never a vote
SYNTHETIC_PREFIX = "syn"  # simulated annotators may be analysed elsewhere but never imported as people
AUTHOR = "author"  # the case writer's own labels: kept for bias analysis, never used for gold
SHEET_COLUMNS = ("id", "category", "goal", "current_state", "history", "proposed_action", "label", "note")
_CASE_FIELDS = ("id", "context_id", "category", "goal", "current_state", "history", "proposed_action")
_ANNOTATOR_NAME = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_LABEL_ALIASES = {
    "necessary": "necessary", "n": "necessary", "nec": "necessary",
    "unnecessary": "unnecessary", "u": "unnecessary", "unnec": "unnecessary",
    "uncertain": "uncertain", "?": "uncertain", "unc": "uncertain",
    "skip": SKIP, "看不懂": SKIP,
}  # fmt: skip


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_cases(path: Path | None = None) -> list[dict[str, Any]]:
    cases = _read_jsonl(path or CASES_PATH)
    for case in cases:
        missing = [name for name in _CASE_FIELDS if name not in case]
        if missing:
            raise ValueError(f"case {case.get('id', '?')} is missing {missing}")
        ActionContext.from_dict(case)  # schema check; raises ContextValidationError
    ids = [case["id"] for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    return cases


def validate_annotator(name: str) -> str:
    if not _ANNOTATOR_NAME.match(name):
        raise ValueError("annotator name must be 1-32 chars of a-z, 0-9, '_' or '-'")
    if name == AUTHOR:
        raise ValueError(f"'{AUTHOR}' is reserved for the case writer's labels")
    if name.startswith(SYNTHETIC_PREFIX):
        # Simulated annotators derived from the author's labels would turn gold into the author's labels.
        raise ValueError(f"names starting with '{SYNTHETIC_PREFIX}' are reserved for synthetic data, which never counts as a person")
    return name


def parse_label(raw: str) -> str | None:
    value = raw.strip().lower()
    if not value:
        return None
    if value not in _LABEL_ALIASES:
        raise ValueError(f"unknown label {raw!r}; use necessary/unnecessary/uncertain/skip (or n/u/?)")
    return _LABEL_ALIASES[value]


# ------------------------------------------------------------------- sheets

def render_action(action: Mapping[str, Any]) -> str:
    text = f"{action.get('tool') or action.get('type', '')}: {action.get('description', '')}"
    arguments = action.get("arguments") or {}
    return f"{text} {json.dumps(arguments, ensure_ascii=False)}" if arguments else text


def render_history(history: Sequence[Mapping[str, Any]]) -> str:
    if not history:
        return "(no previous actions)"
    return "\n".join(
        f"{n}. {render_action(item['action'])}\n   -> {item.get('result', '')}" for n, item in enumerate(history, start=1)
    )


def _safe_cell(text: str) -> str:
    # Spreadsheets execute cells starting with these characters as formulas.
    return "'" + text if text[:1] in ("=", "+", "-", "@") else text


def export_sheet(cases: Sequence[Mapping[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as out:
        writer = csv.writer(out)
        writer.writerow(SHEET_COLUMNS)
        for case in cases:
            cells = [case["id"], case["category"], case["goal"], case["current_state"] or "(none)",
                     render_history(case["history"]), render_action(case["proposed_action"]), "", ""]  # fmt: skip
            writer.writerow([_safe_cell(str(cell)) for cell in cells])


def import_sheet(path: Path, known_ids: Iterable[str], allow_partial: bool = False) -> list[dict[str, str]]:
    known = set(known_ids)
    rows: list[dict[str, str]] = []
    unlabelled = 0
    with path.open(encoding="utf-8-sig", newline="") as source:
        for line, row in enumerate(csv.DictReader(source), start=2):
            if row.get("id") not in known:
                raise ValueError(f"{path}:{line}: unknown case id {row.get('id')!r}")
            label = parse_label(row.get("label") or "")
            if label is None:
                unlabelled += 1
            elif label != SKIP:
                rows.append({"id": row["id"], "label": label, "note": (row.get("note") or "").strip()})
    if unlabelled and not allow_partial:
        raise ValueError(f"{unlabelled} cases have no label (use --allow-partial to import anyway)")
    return rows


def import_web_document(
    document: Mapping[str, Any], known_ids: Iterable[str], annotator: str | None = None
) -> tuple[str, str, list[dict[str, str]]]:
    """Validate one annotator's document saved by the web labeling page.

    Accepts the page's body or a database record wrapping it in ``data``.
    The page stores a free-text display name, so ``annotator`` supplies the
    code name when the document has no valid one. Returns (annotator, task
    set, label rows); the page's content is untrusted input.
    """
    body = document.get("data", document)
    if not isinstance(body, Mapping) or not isinstance(body.get("labels"), Mapping):
        raise ValueError("not a labeling-page document (missing 'labels')")
    if body.get("synthetic") is True:
        raise ValueError("synthetic labels are not annotations by people and cannot be imported")
    annotator = validate_annotator(annotator or str(body.get("annotator", "")))
    known = set(known_ids)
    rows = []
    for case_id, entry in body["labels"].items():
        if case_id not in known:
            raise ValueError(f"{annotator}: unknown case id {case_id!r}")
        if not isinstance(entry, Mapping):
            raise ValueError(f"{annotator}: malformed entry for {case_id}")
        label = parse_label(str(entry.get("label") or ""))
        if label not in (None, SKIP):
            rows.append({"id": case_id, "label": label, "note": str(entry.get("note") or "").strip()[:300]})
    return annotator, str(body.get("set", "")), sorted(rows, key=lambda row: row["id"])


def code_groups(cases: Sequence[Mapping[str, Any]], pilot: Sequence[str]) -> dict[str, list[list[str]]]:
    """Candidate ids per scenario, in the labeling page's order, for each task set."""
    by_context: dict[str, list[str]] = {}
    for case in cases:
        by_context.setdefault(case["context_id"], []).append(case["id"])
    contexts = [case["context_id"] for case in cases]
    return {s: [by_context[c] for c in answer_code.scenario_order(contexts, pilot, s)] for s in ("pilot", "full")}


def read_pilot() -> list[str]:
    lines = (line.strip() for line in PILOT_PATH.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def record_background(annotator: str, programmer: bool | None) -> None:
    """Remember whether an annotator writes code, so expert and lay labels can be analysed apart."""
    path = LABELS_DIR / BACKGROUND_FILE
    records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    records[annotator] = {"programmer": programmer}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


# -------------------------------------------------------------- annotations

def load_annotations(labels_dir: Path | None = None, include_author: bool = False) -> dict[str, dict[str, str]]:
    annotations = {}
    for path in sorted((labels_dir or LABELS_DIR).glob("*.jsonl")):
        if path.stem == AUTHOR and not include_author:
            continue
        annotations[path.stem] = {row["id"]: row["label"] for row in _read_jsonl(path)}
    return annotations


def load_adjudication(path: Path | None = None) -> dict[str, str]:
    path = path or ADJUDICATION_PATH
    return {row["id"]: row["label"] for row in _read_jsonl(path)} if path.exists() else {}


def gold_rows(cases: Sequence[Mapping[str, Any]], gold: Mapping[str, str], voters: Sequence[str]) -> list[dict[str, Any]]:
    """Gold cases in the benchmark runner's format."""
    reason = f"gold label from independent annotators: {', '.join(voters)}"
    return [{**case, "expected": gold[case["id"]], "reason": reason} for case in cases if case["id"] in gold]


# ---------------------------------------------------------------- commands

def select_contexts(cases: Sequence[Mapping[str, Any]], context_ids: Iterable[str]) -> list[Mapping[str, Any]]:
    wanted = set(context_ids)
    unknown = wanted - {case["context_id"] for case in cases}
    if unknown:
        raise ValueError(f"unknown context ids: {sorted(unknown)}")
    return [case for case in cases if case["context_id"] in wanted]


def _cmd_export(args: argparse.Namespace) -> int:
    cases = load_cases()
    if args.contexts:
        lines = (line.strip() for line in Path(args.contexts).read_text(encoding="utf-8").splitlines())
        cases = select_contexts(cases, [line for line in lines if line and not line.startswith("#")])
    export_sheet(cases, Path(args.out))
    print(f"wrote {len(cases)} cases to {args.out}")
    return 0


def _cmd_import(args: argparse.Namespace) -> int:
    name = validate_annotator(args.annotator)
    rows = import_sheet(Path(args.sheet), (c["id"] for c in load_cases()), args.allow_partial)
    _write_jsonl(LABELS_DIR / f"{name}.jsonl", rows)
    print(f"imported {len(rows)} labels for {name}")
    return 0


def _cmd_import_web(args: argparse.Namespace) -> int:
    if args.annotator and len(args.documents) != 1:
        raise ValueError("--annotator names one person, so pass exactly one document with it")
    known = [c["id"] for c in load_cases()]
    for source in args.documents:
        document = json.loads(Path(source).read_text(encoding="utf-8"))
        annotator, task_set, rows = import_web_document(document, known, args.annotator)
        _write_jsonl(LABELS_DIR / f"{annotator}.jsonl", rows)
        body = document.get("data", document)
        record_background(annotator, body.get("programmer") if isinstance(body.get("programmer"), bool) else None)
        print(f"imported {len(rows)} labels for {annotator} (task set: {task_set or 'unknown'})")
    return 0


def _cmd_import_code(args: argparse.Namespace) -> int:
    name = validate_annotator(args.annotator)
    text = Path(args.code).read_text(encoding="utf-8") if Path(args.code).is_file() else args.code
    decoded = answer_code.decode(text, code_groups(load_cases(), read_pilot()))
    rows = [{"id": cid, "label": label, "note": ""} for cid, label in sorted(decoded.labels.items()) if label != SKIP]
    _write_jsonl(LABELS_DIR / f"{name}.jsonl", rows)
    record_background(name, decoded.programmer)
    skipped = sum(1 for label in decoded.labels.values() if label == SKIP)
    print(f"imported {len(rows)} labels for {name} ({decoded.task_set}; {skipped} marked 'don't understand')")
    return 0


def _cmd_agree(args: argparse.Namespace) -> int:
    annotations = load_annotations(include_author=True)
    if len(annotations) < 2:
        raise ValueError("need labels from at least two annotators")
    pairs = all_pairs(annotations)
    print(format_pairs(pairs))
    if args.show_disagreements:
        for pair in pairs:
            print(f"\n{pair.first} vs {pair.second}: {', '.join(pair.disagreements) or 'none'}")
    return 0


def _cmd_gold(args: argparse.Namespace) -> int:
    cases = load_cases()
    annotations = load_annotations()
    result = build_gold(annotations, load_adjudication(), min_votes=args.min_votes, min_share=args.min_share)
    rows = gold_rows(cases, result.labels, sorted(annotations))
    test = [row for row in rows if in_test_split(row["context_id"], args.test_fraction)]
    dev = [row for row in rows if not in_test_split(row["context_id"], args.test_fraction)]
    _write_jsonl(V1_DIR / "gold-dev.jsonl", dev)
    _write_jsonl(V1_DIR / "gold-test.jsonl", test)
    print(f"gold: {len(rows)} cases ({len(dev)} dev, {len(test)} test)")
    print(f"disputed (need adjudication): {len(result.disputed)} {list(result.disputed)[:20]}")
    print(f"under-labelled: {len(result.under_labelled)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m benchmarks.labeling")
    sub = parser.add_subparsers(dest="command", required=True)
    export = sub.add_parser("export", help="write a blank labeling sheet (CSV)")
    export.add_argument("--out", default="labeling-sheet.csv")
    export.add_argument("--contexts", help="file listing context ids to export (e.g. benchmarks/v1/pilot.txt)")
    export.set_defaults(handler=_cmd_export)
    imp = sub.add_parser("import", help="import a filled sheet as one annotator's labels")
    imp.add_argument("sheet")
    imp.add_argument("--annotator", required=True)
    imp.add_argument("--allow-partial", action="store_true")
    imp.set_defaults(handler=_cmd_import)
    web = sub.add_parser("import-web", help="import documents saved by the web labeling page (JSON files)")
    web.add_argument("documents", nargs="+")
    web.add_argument("--annotator", help="code name to use when the document only has a display name")
    web.set_defaults(handler=_cmd_import_web)
    code = sub.add_parser("import-code", help="import an answer code (text, or a file containing it)")
    code.add_argument("code")
    code.add_argument("--annotator", required=True)
    code.set_defaults(handler=_cmd_import_code)
    agree = sub.add_parser("agree", help="pairwise agreement between all annotators (including author)")
    agree.add_argument("--show-disagreements", action="store_true")
    agree.set_defaults(handler=_cmd_agree)
    gold = sub.add_parser("gold", help="build gold dev/test sets from independent annotators")
    gold.add_argument("--test-fraction", type=float, default=0.6)
    gold.add_argument("--min-votes", type=int, default=2)
    gold.add_argument("--min-share", type=float, default=2 / 3, help="share of votes a label needs to become gold")
    gold.set_defaults(handler=_cmd_gold)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
