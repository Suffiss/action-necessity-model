import pytest

from benchmarks.metrics import compute_metrics, confusion_matrix, format_metrics


def test_perfect_predictions() -> None:
    labels = ["necessary", "unnecessary", "uncertain", "necessary"]
    metrics = compute_metrics(labels, labels)
    assert metrics.accuracy == 1.0
    assert metrics.false_unnecessary_rate == 0.0
    assert all(scores.f1 == 1.0 for scores in metrics.per_class.values())


def test_safety_and_reduction_rates() -> None:
    expected = ["necessary", "necessary", "necessary", "necessary", "unnecessary", "unnecessary"]
    predicted = ["necessary", "unnecessary", "uncertain", "necessary", "unnecessary", "uncertain"]
    metrics = compute_metrics(expected, predicted)
    assert metrics.false_unnecessary_rate == pytest.approx(1 / 4)
    assert metrics.unnecessary_action_detection_rate == pytest.approx(1 / 2)
    assert metrics.potential_action_reduction_rate == pytest.approx(2 / 6)
    assert metrics.uncertain_rate == pytest.approx(2 / 6)
    assert metrics.per_class["unnecessary"].precision == pytest.approx(1 / 2)
    assert metrics.per_class["necessary"].recall == pytest.approx(2 / 4)


def test_confusion_matrix_counts_rows_by_expected_label() -> None:
    matrix = confusion_matrix(["necessary", "necessary"], ["unnecessary", "necessary"])
    assert matrix["necessary"] == {"necessary": 1, "unnecessary": 1, "uncertain": 0}


def test_empty_denominators_report_zero() -> None:
    metrics = compute_metrics(["unnecessary"], ["unnecessary"])
    assert metrics.false_unnecessary_rate == 0.0
    assert metrics.per_class["necessary"].precision == 0.0


@pytest.mark.parametrize(("expected", "predicted"), [(["necessary"], []), (["maybe"], ["necessary"])])
def test_invalid_inputs_are_rejected(expected: list[str], predicted: list[str]) -> None:
    with pytest.raises(ValueError):
        compute_metrics(expected, predicted)


def test_report_mentions_headline_metrics() -> None:
    report = format_metrics(compute_metrics(["necessary"], ["necessary"]))
    assert "False unnecessary rate" in report
    assert "Confusion matrix" in report
