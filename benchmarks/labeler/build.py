"""Build the self-contained web labeling page from benchmarks/v1/cases.jsonl.

Usage (from the repository root):  python -m benchmarks.labeler.build [--dist DIR]

Writes two files:
  labeler.html  page body for publishing as a claude.ai artifact (the host adds the document skeleton)
  index.html    complete standalone page for any static host (GitHub Pages) or opening locally

The page embeds the cases grouped by scenario and the pilot list. It never
reads labels/ : annotators must not be able to see anyone's answers.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from benchmarks.labeling import V1_DIR, load_cases

TEMPLATE = Path(__file__).with_name("template.html")
DIST = Path(__file__).with_name("dist")
PLACEHOLDER = "__LABELER_DATA__"
STANDALONE_HEAD = (
    '<!doctype html><html lang="zh"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body>'
)
STANDALONE_TAIL = "</body></html>\n"


def group_scenarios(cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    scenarios: dict[str, dict[str, Any]] = {}
    for case in cases:
        scenario = scenarios.setdefault(case["context_id"], {
            "context_id": case["context_id"], "category": case["category"], "goal": case["goal"],
            "state": case["current_state"], "history": case["history"], "candidates": [],
        })  # fmt: skip
        if scenario["goal"] != case["goal"] or scenario["history"] != case["history"]:
            raise ValueError(f"{case['id']}: cases of one scenario must share goal and history")
        scenario["candidates"].append({"id": case["id"], "action": case["proposed_action"]})
    return list(scenarios.values())


def read_pilot(path: Path) -> list[str]:
    lines = (line.strip() for line in path.read_text(encoding="utf-8").splitlines())
    return [line for line in lines if line and not line.startswith("#")]


def page_data(cases: Sequence[Mapping[str, Any]], pilot: Sequence[str]) -> str:
    payload = {"scenarios": group_scenarios(cases), "pilot": list(pilot)}
    text = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    # Keep case text from closing the surrounding <script> element.
    return text.replace("</", "<\\/")


def render() -> str:
    template = TEMPLATE.read_text(encoding="utf-8")
    if template.count(PLACEHOLDER) != 1:
        raise ValueError("template must contain the data placeholder exactly once")
    return template.replace(PLACEHOLDER, page_data(load_cases(), read_pilot(V1_DIR / "pilot.txt")))


def build(dist: Path = DIST) -> list[Path]:
    page = render()
    outputs = {dist / "labeler.html": page, dist / "index.html": STANDALONE_HEAD + page + STANDALONE_TAIL}
    dist.mkdir(parents=True, exist_ok=True)
    for path, html in outputs.items():
        path.write_text(html, encoding="utf-8", newline="\n")
    return list(outputs)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m benchmarks.labeler.build")
    parser.add_argument("--dist", type=Path, default=DIST)
    for out in build(parser.parse_args(argv).dist):
        print(f"wrote {out} ({out.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
