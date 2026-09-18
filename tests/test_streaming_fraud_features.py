import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "databricks" / "src"))

pyspark = pytest.importorskip("pyspark")

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from transformations.streaming_fraud_features import (  # noqa: E402
    add_velocity_spike_flag,
    add_windowed_velocity_features,
)


@pytest.fixture(scope="module")
def spark():
    return SparkSession.builder.master("local[2]").appName("test-streaming-fraud-features").getOrCreate()


def test_windowed_velocity_features_aggregates_per_account(spark):
    # Two txns in the same 5-minute tumbling bucket, one in the next bucket.
    df = spark.createDataFrame(
        [
            ("a1", "t1", "2024-01-01 10:00:10", 100.0, "electronics"),
            ("a1", "t2", "2024-01-01 10:00:40", 250.0, "electronics"),
            ("a1", "t3", "2024-01-01 10:06:00", 50.0, "grocery"),
        ],
        ["account_id", "transaction_id", "transaction_ts", "amount", "merchant_category"],
    ).withColumn("transaction_ts", F.to_timestamp("transaction_ts"))

    rows = add_windowed_velocity_features(
        df, window_duration="5 minutes", slide_duration="5 minutes"
    ).collect()

    # Non-overlapping (tumbling) windows here, so totals across all windows must match the input.
    assert sum(r["txn_count_windowed"] for r in rows) == 3
    assert sum(r["txn_amount_sum_windowed"] for r in rows) == pytest.approx(400.0)

    first_window = next(r for r in rows if r["txn_count_windowed"] == 2)
    assert first_window["account_id"] == "a1"
    assert first_window["txn_amount_sum_windowed"] == pytest.approx(350.0)
    assert first_window["distinct_merchant_categories_windowed"] == 1


def test_velocity_spike_flag_triggers_on_either_threshold(spark):
    df = spark.createDataFrame(
        [
            ("a1", 2, 6000.0),  # over amount threshold
            ("a2", 12, 100.0),  # over count threshold
            ("a3", 2, 100.0),  # under both
        ],
        ["account_id", "txn_count_windowed", "txn_amount_sum_windowed"],
    )

    out = {
        row["account_id"]: row["is_velocity_spike"]
        for row in add_velocity_spike_flag(df, count_threshold=10, amount_threshold=5000.0).collect()
    }

    assert out["a1"] is True
    assert out["a2"] is True
    assert out["a3"] is False
