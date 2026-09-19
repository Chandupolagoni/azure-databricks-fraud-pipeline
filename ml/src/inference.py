"""Batch scoring: loads the current Production model from the MLflow Registry and
scores the latest Gold `fraud_features`, writing results back to Delta and to
Snowflake `MARTS.FRAUD_RISK_SCORES` (via the Snowflake connector).

A real-time path fronts this same registered model with a Databricks Model Serving
endpoint invoked synchronously at authorization time instead; see `serving.py` for
the endpoint deploy + scoring helpers.
"""

import argparse

import mlflow
import pandas as pd

from feature_store import FEATURE_COLUMNS

MODEL_NAME = "fraud-risk-classifier"
FLAG_THRESHOLD = 0.5


def score_batch(features_df: pd.DataFrame, stage: str = "Production") -> pd.DataFrame:
    model_uri = f"models:/{MODEL_NAME}/{stage}"
    model = mlflow.sklearn.load_model(model_uri)

    p_fraud = model.predict_proba(features_df[FEATURE_COLUMNS])[:, 1]

    return pd.DataFrame(
        {
            "transaction_id": features_df["transaction_id"],
            "model_version": stage,
            "p_fraud": p_fraud,
            "is_flagged": p_fraud >= FLAG_THRESHOLD,
        }
    )


def write_scores_to_snowflake(scores_df: pd.DataFrame, connection_params: dict) -> None:
    """Writes scored batch to MARTS.FRAUD_RISK_SCORES via the Snowflake Python connector.

    Kept as a thin wrapper so it can be mocked in tests; connection_params should come
    from Key Vault-backed secrets, never hardcoded.
    """
    import snowflake.connector
    from snowflake.connector.pandas_tools import write_pandas

    with snowflake.connector.connect(**connection_params) as conn:
        write_pandas(conn, scores_df, table_name="FRAUD_RISK_SCORES", schema="MARTS")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="Production")
    args = parser.parse_args()

    from feature_store import make_synthetic_training_frame

    sample = make_synthetic_training_frame(n_rows=1000)
    scored = score_batch(sample, stage=args.stage)
    print(scored.head())
    print(f"Flagged {scored['is_flagged'].sum()} of {len(scored)} transactions")
