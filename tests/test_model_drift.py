import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "ml" / "src"))

pytest.importorskip("sklearn")

from monitor_drift import (  # noqa: E402
    DRIFT_TOLERANCE,
    PROMOTION_AUC_PR_THRESHOLD,
    build_drift_alert_message,
    check_promotion_gate_drift,
    compute_live_auc_pr,
    run_drift_check,
)


def _reconciled_frame(n: int, separable: bool = True) -> pd.DataFrame:
    """n rows, half fraud/half not; p_fraud either cleanly separates the classes
    (high live AUC-PR) or is pure noise (low live AUC-PR), for testing both branches
    of the drift check.
    """
    is_fraud = [1 if i % 2 == 0 else 0 for i in range(n)]
    if separable:
        p_fraud = [0.9 if f else 0.1 for f in is_fraud]
    else:
        # Alternates independently of the label — no discriminative signal.
        p_fraud = [0.5 + 0.01 * (i % 3) for i in range(n)]

    return pd.DataFrame(
        {
            "transaction_id": [f"txn_{i}" for i in range(n)],
            "model_version": "Production",
            "p_fraud": p_fraud,
            "is_flagged": [p >= 0.5 for p in p_fraud],
            "is_fraud": is_fraud,
        }
    )


def test_compute_live_auc_pr_returns_none_below_min_samples():
    thin_sample = _reconciled_frame(50)

    assert compute_live_auc_pr(thin_sample, min_samples=200) is None


def test_compute_live_auc_pr_returns_metrics_above_min_samples():
    sample = _reconciled_frame(400)

    metrics = compute_live_auc_pr(sample, min_samples=200)

    assert metrics is not None
    assert "auc_pr" in metrics
    assert metrics["auc_pr"] > 0.9


def test_check_promotion_gate_drift_flags_when_below_gate_minus_tolerance():
    live_metrics = {"auc_pr": PROMOTION_AUC_PR_THRESHOLD - DRIFT_TOLERANCE - 0.01}

    result = check_promotion_gate_drift(live_metrics)

    assert result["drifted"] is True
    assert result["delta"] < 0


def test_check_promotion_gate_drift_tolerates_small_dip_below_gate():
    live_metrics = {"auc_pr": PROMOTION_AUC_PR_THRESHOLD - DRIFT_TOLERANCE + 0.005}

    result = check_promotion_gate_drift(live_metrics)

    assert result["drifted"] is False


def test_check_promotion_gate_drift_not_flagged_above_gate():
    live_metrics = {"auc_pr": PROMOTION_AUC_PR_THRESHOLD + 0.1}

    result = check_promotion_gate_drift(live_metrics)

    assert result["drifted"] is False
    assert result["delta"] > 0


def test_build_drift_alert_message_includes_key_figures():
    drift_result = check_promotion_gate_drift({"auc_pr": 0.40})

    message = build_drift_alert_message(drift_result, model_version="7", window_days=30, sample_size=512)

    assert "fraud-risk-classifier" in message
    assert "0.4" in message
    assert "512" in message
    assert "train.py" in message


def test_run_drift_check_skips_when_reconciled_sample_too_small():
    with patch("monitor_drift.load_reconciled_scores_from_snowflake", return_value=_reconciled_frame(10)):
        result = run_drift_check(connection_params={}, window_days=30)

    assert result is None


def test_run_drift_check_returns_result_with_model_version_and_window():
    reconciled = _reconciled_frame(400, separable=False)
    with patch("monitor_drift.load_reconciled_scores_from_snowflake", return_value=reconciled):
        result = run_drift_check(connection_params={}, window_days=14)

    assert result is not None
    assert result["model_version"] == "Production"
    assert result["window_days"] == 14
    assert result["sample_size"] == 400
    assert result["drifted"] is True
