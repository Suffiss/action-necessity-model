"""Inter-annotator agreement, gold-label construction and leakage-free splitting.

Labels are ``{case_id: label}`` mappings, one per annotator. Nothing here reads
files; see ``labeling.py`` for I/O and the command line.
"""

from __future__ import annotations

import hashlib
from collections import Counter
from dataclasses import dataclass
from itertools import combinations
from typing import Iterable, Mapping, Sequence

from benchmarks.metrics import LABELS, confusion_matrix

Labels = Mapping[str, str]
SPLIT_SALT = "suffiss-v1"


def cohen_kappa(first: Sequence[str], second: Sequence[str]) -> float:
    """Chance-corrected agreement between two annotators over the same items."""
    if len(first) != len(second) or not first:
        raise ValueError("kappa needs two non-empty label sequences of equal length")
    total = len(first)
    observed = sum(a == b for a, b in zip(first, second)) / total
    counts_a, counts_b = Counter(first), Counter(second)
    expected = sum(counts_a[label] * counts_b[label] for label in LABELS) / total**2
    if expected == 1.0:
        # Both annotators used one identical label throughout: agreement is total but uninformative.
        return 1.0
    return (observed - expected) / (1.0 - expected)


def interpret_kappa(kappa: float) -> str:
    """Landis & Koch (1977) bands; a convention, not a statistical test."""
    for upper, name in ((0.0, "poor"), (0.2, "slight"), (0.4, "fair"), (0.6, "moderate"), (0.8, "substantial")):
        if kappa <= upper:
            return name
    return "almost perfect"


@dataclass(frozen=True)
class PairAgreement:
    first: str
    second: str
    cases: int
    raw_agreement: float
    kappa: float
    confusion: dict[str, dict[str, int]]
    disagreements: tuple[str, ...]


def pair_agreement(name_a: str, labels_a: Labels, name_b: str, labels_b: Labels) -> PairAgreement:
    shared = sorted(set(labels_a) & set(labels_b))
    if not shared:
        raise ValueError(f"{name_a} and {name_b} share no labelled cases")
    first = [labels_a[i] for i in shared]
    second = [labels_b[i] for i in shared]
    return PairAgreement(
        first=name_a,
        second=name_b,
        cases=len(shared),
        raw_agreement=sum(a == b for a, b in zip(first, second)) / len(shared),
        kappa=cohen_kappa(first, second),
        confusion=confusion_matrix(first, second),
        disagreements=tuple(i for i, a, b in zip(shared, first, second) if a != b),
    )


def all_pairs(annotations: Mapping[str, Labels]) -> list[PairAgreement]:
    names = sorted(annotations)
    return [pair_agreement(a, annotations[a], b, annotations[b]) for a, b in combinations(names, 2)]


@dataclass(frozen=True)
class GoldResult:
    labels: dict[str, str]
    disputed: tuple[str, ...]  # necessary vs unnecessary, needs adjudication
    under_labelled: tuple[str, ...]  # fewer annotators than required


DEFAULT_MIN_SHARE = 2 / 3


def combine_votes(votes: Iterable[str], min_share: float = DEFAULT_MIN_SHARE) -> str | None:
    """Gold label from independent votes, or None when adjudication is needed.

    A label backed by at least ``min_share`` of the votes stands; with two
    annotators that means unanimity. Otherwise, a real necessary-vs-unnecessary
    split (each side holding at least the remaining share) is a dispute, and
    any other split means careful readers found the case ambiguous, which is
    what ``uncertain`` denotes. A strict "any disagreement" rule would leave
    almost nothing undisputed once more than a few people label a case.
    """
    counts = Counter(votes)
    total = sum(counts.values())
    if not total:
        raise ValueError("no votes to combine")
    label, top = counts.most_common(1)[0]
    if top / total >= min_share - 1e-9:
        return label
    minority = 1.0 - min_share
    if counts["necessary"] / total >= minority - 1e-9 and counts["unnecessary"] / total >= minority - 1e-9:
        return None
    return "uncertain"


def build_gold(
    annotations: Mapping[str, Labels],
    adjudicated: Labels | None = None,
    min_votes: int = 2,
    min_share: float = DEFAULT_MIN_SHARE,
) -> GoldResult:
    if not 0.5 < min_share <= 1.0:
        raise ValueError("min_share must be above 0.5 (a majority) and at most 1")
    adjudicated = adjudicated or {}
    case_ids = sorted({case_id for labels in annotations.values() for case_id in labels})
    gold: dict[str, str] = {}
    disputed, under = [], []
    for case_id in case_ids:
        votes = [labels[case_id] for labels in annotations.values() if case_id in labels]
        if len(votes) < min_votes:
            under.append(case_id)
            continue
        label = adjudicated.get(case_id) or combine_votes(votes, min_share)
        if label is None:
            disputed.append(case_id)
        else:
            gold[case_id] = label
    return GoldResult(labels=gold, disputed=tuple(disputed), under_labelled=tuple(under))


def in_test_split(context_id: str, test_fraction: float) -> bool:
    """Deterministic split by *context*, so variants of one scenario never straddle dev and test."""
    if not 0.0 <= test_fraction <= 1.0:
        raise ValueError("test_fraction must be within [0, 1]")
    digest = hashlib.sha256(f"{SPLIT_SALT}:{context_id}".encode()).hexdigest()
    return int(digest, 16) % 10_000 < round(test_fraction * 10_000)


def format_pairs(pairs: Sequence[PairAgreement]) -> str:
    lines = [f"{'pair':<28} {'cases':>5} {'agree':>6} {'kappa':>6}  interpretation"]
    for p in pairs:
        name = f"{p.first} vs {p.second}"
        lines.append(f"{name:<28} {p.cases:>5} {p.raw_agreement:>6.1%} {p.kappa:>6.2f}  {interpret_kappa(p.kappa)}")
    return "\n".join(lines)
