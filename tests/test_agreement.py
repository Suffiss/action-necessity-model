import pytest

from benchmarks.agreement import (
    all_pairs,
    build_gold,
    cohen_kappa,
    combine_votes,
    in_test_split,
    interpret_kappa,
    pair_agreement,
)

N, U, Q = "necessary", "unnecessary", "uncertain"


def test_kappa_matches_hand_computation() -> None:
    # observed 3/4, expected (2*1 + 2*3)/16 = 1/2  ->  (0.75 - 0.5) / 0.5
    assert cohen_kappa([N, N, U, U], [N, U, U, U]) == pytest.approx(0.5)


def test_kappa_perfect_and_chance_level() -> None:
    assert cohen_kappa([N, U, Q], [N, U, Q]) == pytest.approx(1.0)
    assert cohen_kappa([N, N, U, U], [N, U, N, U]) == pytest.approx(0.0)


def test_kappa_with_single_shared_label_is_total_agreement() -> None:
    assert cohen_kappa([N, N], [N, N]) == 1.0


@pytest.mark.parametrize(("first", "second"), [([], []), ([N], [N, U])])
def test_kappa_rejects_bad_input(first: list[str], second: list[str]) -> None:
    with pytest.raises(ValueError):
        cohen_kappa(first, second)


@pytest.mark.parametrize(("kappa", "band"), [(-0.1, "poor"), (0.15, "slight"), (0.5, "moderate"), (0.9, "almost perfect")])
def test_interpret_kappa(kappa: float, band: str) -> None:
    assert interpret_kappa(kappa) == band


def test_pair_agreement_uses_only_shared_cases() -> None:
    pair = pair_agreement("ann", {"a": N, "b": U, "c": Q}, "bob", {"a": N, "b": N})
    assert pair.cases == 2
    assert pair.raw_agreement == pytest.approx(0.5)
    assert pair.disagreements == ("b",)


def test_all_pairs_covers_every_annotator_pair() -> None:
    labels = {"x": {"a": N}, "y": {"a": N}, "z": {"a": U}}
    assert [(p.first, p.second) for p in all_pairs(labels)] == [("x", "y"), ("x", "z"), ("y", "z")]


@pytest.mark.parametrize(
    ("votes", "expected"),
    [([N, N], N), ([U, U], U), ([N, Q], Q), ([U, Q], Q), ([N, U], None), ([N, U, Q], None)],
)
def test_combine_votes(votes: list[str], expected: str | None) -> None:
    assert combine_votes(votes) == expected


@pytest.mark.parametrize(
    ("votes", "expected"),
    [
        ([N] * 7 + [U] * 2 + [Q], N),  # 70% clears the two-thirds bar
        ([U] * 5 + [N] * 4 + [Q], None),  # a genuine split between the two decisive labels
        ([N] * 5 + [Q] * 5, Q),  # torn only between "necessary" and "unsure"
        ([N] * 6 + [U] * 3, N),  # exactly two thirds
    ],
)
def test_combine_votes_with_many_annotators(votes: list[str], expected: str | None) -> None:
    assert combine_votes(votes) == expected


def test_supermajority_recovers_truth_from_many_noisy_voters() -> None:
    # 25 independent voters who each match the truth 75% of the time: a strict
    # "any disagreement is a dispute" rule would dispute every case.
    import random

    rng = random.Random(7)
    truth = {f"c{i}": rng.choice([N, U, Q]) for i in range(200)}
    annotations = {
        f"a{j}": {c: (t if rng.random() < 0.75 else rng.choice([N, U, Q])) for c, t in truth.items()} for j in range(25)
    }
    gold = build_gold(annotations)
    recovered = sum(gold.labels.get(c) == t for c, t in truth.items())
    assert recovered >= 190
    assert len(gold.disputed) <= 5


@pytest.mark.parametrize("share", [0.5, 0.3, 1.2])
def test_build_gold_rejects_non_majority_thresholds(share: float) -> None:
    with pytest.raises(ValueError):
        build_gold({"a": {"x": N}, "b": {"x": N}}, min_share=share)


def test_build_gold_reports_disputes_and_under_labelled_cases() -> None:
    annotations = {"ann": {"a": N, "b": N, "c": U}, "bob": {"a": N, "b": U}}
    result = build_gold(annotations)
    assert result.labels == {"a": N}
    assert result.disputed == ("b",)
    assert result.under_labelled == ("c",)


def test_adjudication_resolves_disputes() -> None:
    annotations = {"ann": {"b": N}, "bob": {"b": U}}
    assert build_gold(annotations, adjudicated={"b": Q}).labels == {"b": Q}


def test_split_is_deterministic_and_roughly_proportional() -> None:
    contexts = [f"ctx-{i}" for i in range(2000)]
    first = [in_test_split(c, 0.6) for c in contexts]
    assert first == [in_test_split(c, 0.6) for c in contexts]
    assert 0.55 < sum(first) / len(first) < 0.65
    assert not any(in_test_split(c, 0.0) for c in contexts)
    assert all(in_test_split(c, 1.0) for c in contexts)


def test_split_rejects_invalid_fraction() -> None:
    with pytest.raises(ValueError):
        in_test_split("ctx", 1.5)
