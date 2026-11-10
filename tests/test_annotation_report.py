from benchmarks.annotation_report import (
    agreement_by_background,
    agreement_by_category,
    annotator_rows,
    author_bias,
    background_of,
    disputed_cases,
    format_report,
    skip_hotspots,
)

N, U, Q = "necessary", "unnecessary", "uncertain"
ANNOTATIONS = {
    "ann": {"c1": N, "c2": U, "c3": Q, "c4": N},
    "bob": {"c1": N, "c2": U, "c3": U, "c4": U},
    "eve": {"c1": N, "c2": N, "c3": Q, "c4": N},
}
BACKGROUNDS = {
    "ann": {"programmer": True, "skipped": ["c5"]},
    "bob": {"programmer": True, "skipped": ["c5", "c6"]},
    "eve": {"programmer": False, "skipped": []},
}
AUTHOR = {"c1": N, "c2": U, "c3": U, "c4": U}
CATEGORIES = {"c1": "coding", "c2": "coding", "c3": "browser", "c4": "browser"}


def test_background_labels() -> None:
    assert [background_of(n, BACKGROUNDS) for n in ("ann", "eve", "zed")] == ["codes", "does not code", "unknown"]


def test_annotator_rows_count_labels_and_skips() -> None:
    rows = {r["annotator"]: r for r in annotator_rows(ANNOTATIONS, BACKGROUNDS)}
    assert rows["bob"] == {
        "annotator": "bob", "background": "codes", "labelled": 4, "skipped": 2, "necessary": 1, "unnecessary": 3, "uncertain": 0,
    }  # fmt: skip


def test_agreement_is_grouped_by_kind_of_pair() -> None:
    groups = agreement_by_background(ANNOTATIONS, BACKGROUNDS)
    assert set(groups) == {"both code", "one codes, one does not"}
    assert groups["both code"]["pairs"] == 1
    assert groups["one codes, one does not"]["pairs"] == 2


def test_author_bias_counts_both_directions() -> None:
    # stricter: author U where a person said N (eve on c2, ann and eve on c4); looser: none.
    assert author_bias(AUTHOR, ANNOTATIONS) == {"compared": 12, "agree": 7, "stricter": 3, "looser": 0}


def test_agreement_by_category() -> None:
    shares = agreement_by_category(ANNOTATIONS, CATEGORIES)
    # coding: c1 3/3 pairs agree, c2 1/3 -> 4/6; browser: c3 1/3, c4 1/3 -> 2/6
    assert shares == {"browser": 2 / 6, "coding": 4 / 6}


def test_skip_hotspots_are_ranked() -> None:
    assert skip_hotspots(BACKGROUNDS) == [("c5", 2), ("c6", 1)]


def test_disputed_cases_need_a_strong_split() -> None:
    # In ANNOTATIONS every split is 2-to-1, which the two-thirds rule resolves.
    assert disputed_cases(ANNOTATIONS) == []
    split = {"a": {"x": N, "y": N, "z": U}, "b": {"x": U, "y": N, "z": Q}}
    assert disputed_cases(split) == ["x"]


def test_report_names_every_section() -> None:
    report = format_report(ANNOTATIONS, BACKGROUNDS, AUTHOR, CATEGORIES)
    for heading in ("Annotators:", "Agreement by background", "Author vs annotators:", "Agreement by category", "Most skipped", "Disputed cases"):
        assert heading in report
    assert "author stricter (author unnecessary, person necessary): 3" in report


def test_report_handles_no_annotations() -> None:
    assert "(none)" in format_report({}, {}, AUTHOR, CATEGORIES)
