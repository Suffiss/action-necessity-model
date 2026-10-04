"""Compact answer codes that annotators can screenshot instead of exporting files.

Format (whitespace-insensitive; the labeling page renders it in exactly this form):

    V1-P-L                       version, task set (P pilot / F full), background (C codes / L does not / U unknown)
    01:12312 02:21133 ...        one group per scenario in page order, one digit per candidate
    CHK 42                       weighted checksum, so a misread digit is caught

Digits: 1 necessary, 2 unnecessary, 3 uncertain, 0 "don't understand" (skipped), - unanswered.
The page's buildAnswerCode() must stay identical to encode() below.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Sequence

DIGITS = {"necessary": "1", "unnecessary": "2", "uncertain": "3", "skip": "0"}
LABELS = {digit: label for label, digit in DIGITS.items()}
SETS = {"pilot": "P", "full": "F"}
BACKGROUND = {True: "C", False: "L", None: "U"}
_HEADER = re.compile(r"V1-([PF])-([CLU])")
_GROUP = re.compile(r"(\d{2}):([0-3-]{5})")
_CHECK = re.compile(r"CHK\s*(\d{1,2})")


@dataclass(frozen=True)
class DecodedAnswers:
    task_set: str
    programmer: bool | None
    labels: dict[str, str]  # case id -> label, including "skip"; unanswered cases are absent


def scenario_order(context_ids: Sequence[str], pilot: Sequence[str], task_set: str) -> list[str]:
    """Scenarios in page order: dataset order, filtered to the pilot set when asked."""
    ordered = list(dict.fromkeys(context_ids))
    return [c for c in ordered if c in set(pilot)] if task_set == "pilot" else ordered


def checksum(digits: str) -> int:
    # Position-weighted, so swapped or misread digits change the result; "-" counts as 4.
    return sum((i + 1) * (4 if d == "-" else int(d)) for i, d in enumerate(digits)) % 97


def encode(groups: Sequence[Sequence[str]], labels: Mapping[str, str], task_set: str, programmer: bool | None) -> str:
    """``groups`` lists each scenario's candidate ids in page order."""
    rows = [f"{i:02d}:" + "".join(DIGITS.get(labels.get(cid, ""), "-") for cid in ids) for i, ids in enumerate(groups, start=1)]
    digits = "".join(row[3:] for row in rows)
    lines = [f"V1-{SETS[task_set]}-{BACKGROUND[programmer]}"]
    lines += [" ".join(rows[i : i + 5]) for i in range(0, len(rows), 5)]
    lines.append(f"CHK {checksum(digits):02d}")
    return "\n".join(lines)


def decode(text: str, groups_by_set: Mapping[str, Sequence[Sequence[str]]]) -> DecodedAnswers:
    """Parse a (possibly hand-copied) code. Raises ValueError on any inconsistency."""
    header = _HEADER.search(text)
    check = _CHECK.search(text)
    if not header or not check:
        raise ValueError("answer code needs a 'V1-x-x' header and a 'CHK nn' line")
    task_set = {v: k for k, v in SETS.items()}[header.group(1)]
    groups = groups_by_set[task_set]
    found = _GROUP.findall(text)
    if [int(n) for n, _ in found] != list(range(1, len(groups) + 1)):
        raise ValueError(f"expected scenario groups 01..{len(groups):02d} in order, found {len(found)}")
    digits = "".join(d for _, d in found)
    if checksum(digits) != int(check.group(1)):
        raise ValueError("checksum mismatch: a digit was probably misread")
    labels = {cid: LABELS[d] for ids, (_, row) in zip(groups, found) for cid, d in zip(ids, row) if d in LABELS}
    programmer = {v: k for k, v in BACKGROUND.items()}[header.group(2)]
    return DecodedAnswers(task_set=task_set, programmer=programmer, labels=labels)
