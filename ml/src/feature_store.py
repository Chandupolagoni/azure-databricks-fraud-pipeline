"""Loads the Gold `fraud_features` table (+ historical labels) into a training-ready
pandas DataFrame. In production this would read via the Databricks Feature Store API;
kept as a plain Delta read here to keep the example runnable outside Databricks.
"""

import pandas as pd

FEATURE_COLUMNS = [
    "txn_count_1h",
    "txn_amount_sum_1h",
    "txn_count_24h",
    "txn_amount_sum_24h",
    "is_impossible_travel",
    "distinct_accounts_per_device_24h",
    "merchant_risk_score",
]

LABEL_COLUMN = "is_fraud"


def load_training_frame(delta_path: str, labels_path: str) -> pd.DataFrame:
    """Join the engineered features with historical confirmed-fraud labels.

    Both paths are Delta tables; reading via delta-rs/pandas keeps this importable
    in a plain Python environment (e.g. this repo's unit tests / CI) without a
    running Spark cluster.
    """
    from deltalake import DeltaTable

    features = DeltaTable(delta_path).to_pandas()
    labels = DeltaTable(labels_path).to_pandas()[["transaction_id", LABEL_COLUMN]]

    return features.merge(labels, on="transaction_id", how="inner")


def make_synthetic_training_frame(n_rows: int = 5000, seed: int = 42) -> pd.DataFrame:
    """Generates a synthetic dataset with the same schema, for local dev/CI/tests
    where no real Delta/ADLS access is available.
    """
    import numpy as np

    rng = np.random.default_rng(seed)

    df = pd.DataFrame(
        {
            "transaction_id": [f"txn_{i}" for i in range(n_rows)],
            "txn_count_1h": rng.poisson(2, n_rows),
            "txn_amount_sum_1h": rng.exponential(150, n_rows),
            "txn_count_24h": rng.poisson(12, n_rows),
            "txn_amount_sum_24h": rng.exponential(900, n_rows),
            "is_impossible_travel": rng.random(n_rows) < 0.02,
            "distinct_accounts_per_device_24h": rng.poisson(1, n_rows) + 1,
            "merchant_risk_score": rng.beta(2, 5, n_rows),
        }
    )

    # Synthetic fraud label correlated with risk signals, with base-rate noise.
    fraud_score = (
        0.4 * df["is_impossible_travel"].astype(float)
        + 0.3 * (df["distinct_accounts_per_device_24h"] > 3).astype(float)
        + 0.3 * df["merchant_risk_score"]
        + rng.normal(0, 0.1, n_rows)
    )
    df[LABEL_COLUMN] = (fraud_score > fraud_score.quantile(0.97)).astype(int)

    return df
