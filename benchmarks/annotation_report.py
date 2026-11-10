"""Analysis of collected v1 annotations: who labelled what, where people agree, and author bias.

Pure functions over label mappings; ``labeling report`` wires them to the files.
"""

from __future__ import annotations

import statistics
from collections import Counter
from itertools import combinations
from typing import Any, Mapping, Sequence

from benchmarks.agreement import Labels, combine_votes, interpret_kappa, pair_agreement
from benchmarks.metrics import LABELS

Backgrounds = Mapping[str, Mapping[str, Any]]


def background_of(name: str, backgrounds: Backgrounds) -> str:
    programmer = backgrounds.get(name, {}).get("programmer")
    return {True: "codes", False: "does not code"}.get(programmer, "unknown")


def annotator_rows(annotations: Mapping[str, Labels], backgrounds: Backgrounds) -> list[dict[str, Any]]:
    rows = []
    for name, labels in sorted(annotations.items()):
        counts = Counter(labels.values())
        rows.append({
            "annotator": name, "background": background_of(name, backgrounds), "labelled": len(labels),
            "skipped": len(backgrounds.get(name, {}).get("skipped", [])), **{label: counts[label] for label in LABELS},
        })  # fmt: skip
    return rows


def _pair_group(a: str, b: str, backgrounds: Backgrounds) -> str:
    kinds = {background_of(a, backgrounds), background_of(b, backgrounds)}
    if "unknown" in kinds:
        return "involves unknown background"
    return "both code" if kinds == {"codes"} else "neither codes" if kinds == {"does not code"} else "one codes, one does not"


def agreement_by_background(annotations: Mapping[str, Labels], backgrounds: Backgrounds) -> dict[str, dict[str, Any]]:
    """Median pairwise kappa per kind of pair; differences hint at expertise effects."""
    groups: dict[str, list[float]] = {}
    for a, b in combinations(sorted(annotations), 2):
        if len(set(annotations[a]) & set(annotations[b])) < 2:
            continue
        groups.setdefault(_pair_group(a, b, backgrounds), []).append(pair_agreement(a, annotations[a], b, annotations[b]).kappa)
    return {g: {"pairs": len(k), "median_kappa": statistics.median(k)} for g, k in sorted(groups.items())}


def author_bias(author: Labels, annotations: Mapping[str, Labels]) -> dict[str, int]:
    """How often the author's (and so the gate's) view is stricter or looser than people's.

    "stricter" counts cases the author called unnecessary that a person called
    necessary: the direction in which the gate would block needed work.
    """
    totals = Counter()
    for labels in annotations.values():
        for case_id, label in labels.items():
            if case_id not in author:
                continue
            totals["compared"] += 1
            totals["agree"] += author[case_id] == label
            totals["stricter"] += author[case_id] == "unnecessary" and label == "necessary"
            totals["looser"] += author[case_id] == "necessary" and label == "unnecessary"
    return {key: totals[key] for key in ("compared", "agree", "stricter", "looser")}


def agreement_by_category(annotations: Mapping[str, Labels], categories: Mapping[str, str]) -> dict[str, float]:
    """Share of annotator pairs that chose the same label, per case category."""
    hits: Counter[str] = Counter()
    pairs: Counter[str] = Counter()
    for a, b in combinations(sorted(annotations), 2):
        for case_id in set(annotations[a]) & set(annotations[b]):
            category = categories.get(case_id, "unknown")
            pairs[category] += 1
            hits[category] += annotations[a][case_id] == annotations[b][case_id]
    return {category: hits[category] / pairs[category] for category in sorted(pairs)}


def skip_hotspots(backgrounds: Backgrounds, limit: int = 10) -> list[tuple[str, int]]:
    counts = Counter(case_id for record in backgrounds.values() for case_id in record.get("skipped", []))
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]


def disputed_cases(annotations: Mapping[str, Labels]) -> list[str]:
    votes: dict[str, list[str]] = {}
    for labels in annotations.values():
        for case_id, label in labels.items():
            votes.setdefault(case_id, []).append(label)
    return sorted(case_id for case_id, v in votes.items() if len(v) >= 2 and combine_votes(v) is None)


def _section(title: str, lines: Sequence[str]) -> list[str]:
    return ["", title, *(lines or ["  (none)"])]


def format_report(
    annotations: Mapping[str, Labels], backgrounds: Backgrounds, author: Labels, categories: Mapping[str, str]
) -> str:
    lines = [f"Annotators: {len(annotations)} (author's labels compared separately, never counted)"]
    lines += _section("Annotators:", [
        f"  {r['annotator']:<16} {r['background']:<14} labelled {r['labelled']:>3}  skipped {r['skipped']:>3}  "
        f"n/u/q {r['necessary']}/{r['unnecessary']}/{r['uncertain']}" for r in annotator_rows(annotations, backgrounds)
    ])  # fmt: skip
    lines += _section("Agreement by background (median Cohen's kappa):", [
        f"  {group:<28} {d['median_kappa']:.2f} ({interpret_kappa(d['median_kappa'])}), {d['pairs']} pairs"
        for group, d in agreement_by_background(annotations, backgrounds).items()
    ])  # fmt: skip
    bias = author_bias(author, annotations)
    if bias["compared"]:
        lines += _section("Author vs annotators:", [
            f"  agree on {bias['agree']}/{bias['compared']} labels ({bias['agree'] / bias['compared']:.0%})",
            f"  author stricter (author unnecessary, person necessary): {bias['stricter']}  <- the gate's risky direction",
            f"  author looser   (author necessary, person unnecessary): {bias['looser']}",
        ])  # fmt: skip
    lines += _section("Agreement by category (share of pairs choosing the same label):", [
        f"  {category:<14} {share:.0%}" for category, share in agreement_by_category(annotations, categories).items()
    ])  # fmt: skip
    lines += _section("Most skipped (\"don't understand\") cases:", [f"  {cid}  skipped by {n}" for cid, n in skip_hotspots(backgrounds)])
    lines += _section("Disputed cases (strong necessary vs unnecessary split):", [f"  {cid}" for cid in disputed_cases(annotations)])
    return "\n".join(lines)
