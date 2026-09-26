import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "ml" / "src"))

from evaluate import evaluate_predictions  # noqa: E402


def test_perfect_classifier_scores_one():
    y_true = [0, 0, 1, 1]
    y_proba = [0.01, 0.02, 0.98, 0.99]

    metrics = evaluate_predictions(y_true, y_proba)

    assert metrics["auc_pr"] == pytest.approx(1.0)
    assert metrics["auc_roc"] == pytest.approx(1.0)
    assert metrics["precision_at_0.5"] == pytest.approx(1.0)
    assert metrics["recall_at_0.5"] == pytest.approx(1.0)


def test_no_positive_predictions_yields_zero_precision_and_recall():
    y_true = [0, 1, 1, 0]
    y_proba = [0.1, 0.2, 0.3, 0.05]  # every score is below the default 0.5 threshold

    metrics = evaluate_predictions(y_true, y_proba)

    assert metrics["precision_at_0.5"] == 0.0
    assert metrics["recall_at_0.5"] == 0.0


def test_higher_decision_threshold_never_increases_recall():
    y_true = [0, 0, 1, 1]
    y_proba = [0.3, 0.6, 0.6, 0.9]

    lenient = evaluate_predictions(y_true, y_proba, decision_threshold=0.5)
    strict = evaluate_predictions(y_true, y_proba, decision_threshold=0.8)

    assert strict["recall_at_0.5"] <= lenient["recall_at_0.5"]


def test_metrics_are_plain_python_floats():
    y_true = [0, 1, 0, 1]
    y_proba = [0.2, 0.7, 0.4, 0.6]

    metrics = evaluate_predictions(y_true, y_proba)

    for key, value in metrics.items():
        assert isinstance(value, float), f"{key} should be a plain python float, got {type(value)}"


def test_empty_input_raises_value_error():
    with pytest.raises(ValueError, match="at least one sample"):
        evaluate_predictions([], [])


def test_mismatched_lengths_raise_value_error():
    with pytest.raises(ValueError, match="same length"):
        evaluate_predictions([0, 1, 1], [0.2, 0.8])


def test_out_of_range_decision_threshold_raises_value_error():
    with pytest.raises(ValueError, match="decision_threshold"):
        evaluate_predictions([0, 1], [0.2, 0.8], decision_threshold=1.5)
