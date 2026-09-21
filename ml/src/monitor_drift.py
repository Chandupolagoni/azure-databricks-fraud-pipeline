"""Live model-quality drift monitor: reconciles scored transactions against
confirmed-fraud outcomes that land after the chargeback/dispute window closes, and
compares the resulting live AUC-PR back against the same promotion gate `train.py`
uses at training time (`PROMOTION_AUC_PR_THRESHOLD`).

A model can clear the offline promotion gate at training time and still degrade in
production as fraud patterns shift — this closes that gap by re-scoring the gate
against live outcomes on a rolling window, rather than waiting for the next
scheduled retrain to notice.

Reads from `MARTS.VW_RECONCILED_SCORED_TRANSACTIONS` (see
`snowflake/ddl/05_create_fraud_outcomes.sql`), which joins `FRAUD_RISK_SCORES`
against `CONFIRMED_FRAUD_OUTCOMES`. Meant to run as a scheduled Databricks job task,
independent of the daily batch-scoring job in `inference.py`.
"""

from __future__ import annotations

import argparse

import pandas as pd
from evaluate import evaluate_predictions

MODEL_NAME = "fraud-risk-classifier"

# Kept in sync with train.py::PROMOTION_AUC_PR_THRESHOLD by convention (not imported
# directly, since train.py pulls in mlflow/sklearn training deps this module doesn't
# otherwise need) — update both together if the gate ever moves.
PROMOTION_AUC_PR_THRESHOLD = 0.55

# Live traffic is noisier than a held-out test set (smaller reconciled sample, label
# lag, mix shift), so drift is only flagged once the live AUC-PR falls this far below
# the gate rather than on any dip at all.
DRIFT_TOLERANCE = 0.03

# Below this many reconciled outcomes, the live AUC-PR estimate is too noisy to act
# on — skip the check rather than risk a false alarm on a thin sample.
MIN_RECONCILED_SAMPLES = 200


def compute_live_auc_pr(
    reconciled_df: pd.DataFrame, min_samples: int = MIN_RECONCILED_SAMPLES
) -> dict | None:
    """Scores the reconciled (outcome-known) population with the same metrics used
    at training time. Returns None when the sample is too thin to trust.
    """
    if len(reconciled_df) < min_samples:
        return None

    return evaluate_predictions(reconciled_df["is_fraud"], reconciled_df["p_fraud"])


def check_promotion_gate_drift(
    live_metrics: dict,
    gate_threshold: float = PROMOTION_AUC_PR_THRESHOLD,
    tolerance: float = DRIFT_TOLERANCE,
) -> dict:
    """Compares a live AUC-PR reading back against the training-time promotion gate.

    `drifted=True` means live fraud-catching quality has fallen enough below the bar
    the model was promoted on to warrant a retrain, not just training-run noise.
    """
    live_auc_pr = live_metrics["auc_pr"]
    delta = round(live_auc_pr - gate_threshold, 4)

    return {
        "live_auc_pr": round(live_auc_pr, 4),
        "gate_threshold": gate_threshold,
        "tolerance": tolerance,
        "delta": delta,
        "drifted": live_auc_pr < (gate_threshold - tolerance),
    }


def build_drift_alert_message(
    drift_result: dict, model_version: str, window_days: int, sample_size: int
) -> str:
    """Formats the on-call-facing alert body for `email_notifications`-style routing,
    mirroring the failure-alert tone already used for the ETL job (see
    `databricks/jobs/job_config.json`).
    """
    return (
        f"[fraud-risk-classifier] Live model-quality drift detected\n"
        f"  Model version: {model_version}\n"
        f"  Reconciliation window: trailing {window_days} days ({sample_size} outcomes)\n"
        f"  Live AUC-PR: {drift_result['live_auc_pr']} "
        f"(gate: {drift_result['gate_threshold']}, tolerance: {drift_result['tolerance']})\n"
        f"  Delta vs. gate: {drift_result['delta']}\n"
        f"  Action: review recent flagged/missed cases and consider triggering a retrain "
        f"(train.py) ahead of the next scheduled run."
    )


def load_reconciled_scores_from_snowflake(connection_params: dict, window_days: int = 30) -> pd.DataFrame:
    """Pulls the trailing `window_days` of reconciled scores from
    `MARTS.VW_RECONCILED_SCORED_TRANSACTIONS` via the Snowflake Python connector.

    Kept as a thin wrapper so it can be mocked in tests; connection_params should come
    from Key Vault-backed secrets, never hardcoded (same convention as
    `inference.py::write_scores_to_snowflake`).
    """
    import snowflake.connector

    query = f"""
        SELECT transaction_id, model_version, p_fraud, is_flagged, is_fraud
        FROM MARTS.VW_RECONCILED_SCORED_TRANSACTIONS
        WHERE reconciled_at >= DATEADD(day, -{window_days}, CURRENT_TIMESTAMP())
    """
    with snowflake.connector.connect(**connection_params) as conn:
        return pd.read_sql(query, conn)


def run_drift_check(connection_params: dict, window_days: int = 30) -> dict | None:
    """End-to-end check: pull reconciled scores, compute live AUC-PR, compare to the
    gate. Returns None (and skips silently) when there isn't enough reconciled data
    yet to trust the reading.
    """
    reconciled = load_reconciled_scores_from_snowflake(connection_params, window_days=window_days)
    live_metrics = compute_live_auc_pr(reconciled)
    if live_metrics is None:
        return None

    model_version = reconciled["model_version"].mode().iat[0] if len(reconciled) else "unknown"
    result = check_promotion_gate_drift(live_metrics)
    result["model_version"] = model_version
    result["sample_size"] = len(reconciled)
    result["window_days"] = window_days
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--window-days", type=int, default=30)
    args = parser.parse_args()

    from feature_store import make_synthetic_training_frame

    sample = make_synthetic_training_frame(n_rows=2000)
    synthetic_reconciled = pd.DataFrame(
        {
            "transaction_id": sample["transaction_id"],
            "model_version": "Production",
            "p_fraud": sample["is_fraud"].astype(float) * 0.8 + 0.1,
            "is_flagged": sample["is_fraud"].astype(bool),
            "is_fraud": sample["is_fraud"],
        }
    )

    metrics = compute_live_auc_pr(synthetic_reconciled)
    drift = check_promotion_gate_drift(metrics)
    print(drift)
    if drift["drifted"]:
        print(build_drift_alert_message(drift, "Production", args.window_days, len(synthetic_reconciled)))
