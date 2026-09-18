"""Windowed fraud-velocity features computed directly on the streaming Bronze table.

Companion to `transformations.fraud_features.add_transaction_velocity_features`, which computes
the same signal in batch over a fixed trailing-window lookback. This module produces the
streaming equivalent: a stateful `groupBy` windowed aggregation keyed by `account_id`, bounded by
the same late-arrival watermark applied to the Bronze stream
(`utils.streaming_io.apply_late_arrival_watermark`), so a window's result is only emitted once
Spark considers it closed.

This is the second slice of the `[Unreleased]` streaming ingestion path in `docs/CHANGELOG.md`:
`05_streaming_card_auth_ingestion.py` lands the streaming Bronze table, and
`06_streaming_fraud_velocity_features.py` reads it and writes this module's output.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F


def add_windowed_velocity_features(
    df: DataFrame,
    window_duration: str = "5 minutes",
    slide_duration: str = "1 minute",
) -> DataFrame:
    """Sliding-window transaction count/sum/distinct-merchant-category per account.

    Requires `df` to already carry a watermark on `transaction_ts`
    (`streaming_io.apply_late_arrival_watermark`) when called on a streaming DataFrame — the
    watermark is what lets Spark bound state and emit a window as soon as it closes instead of
    keeping state for it indefinitely. `withWatermark` is a no-op on a static DataFrame, so this
    also works unmodified over a batch/backfill read of the Bronze stream's Delta table.
    """
    windowed = df.groupBy(
        F.window("transaction_ts", window_duration, slide_duration).alias("txn_window"),
        "account_id",
    ).agg(
        F.count("transaction_id").alias("txn_count_windowed"),
        F.sum("amount").alias("txn_amount_sum_windowed"),
        F.approx_count_distinct("merchant_category").alias("distinct_merchant_categories_windowed"),
    )

    return (
        windowed.withColumn("window_start", F.col("txn_window.start"))
        .withColumn("window_end", F.col("txn_window.end"))
        .drop("txn_window")
    )


def add_velocity_spike_flag(
    df: DataFrame,
    count_threshold: int = 10,
    amount_threshold: float = 5000.0,
) -> DataFrame:
    """Flags a windowed account bucket as a velocity-spike candidate.

    Thresholds are conservative `dev` defaults, overridden per environment via the notebook's
    widgets the same way `04_feature_engineering.py`'s `storage_account` widget is.
    """
    return df.withColumn(
        "is_velocity_spike",
        (F.col("txn_count_windowed") >= count_threshold)
        | (F.col("txn_amount_sum_windowed") >= amount_threshold),
    )


def write_windowed_features_stream(
    df: DataFrame,
    path: str,
    checkpoint_path: str,
    trigger_seconds: int = 30,
):
    """Append-mode sink for the windowed feature stream.

    Append mode is valid for a stateful windowed aggregation (which would otherwise require
    `update`/`complete` output mode) precisely because the watermark bounds when a window is
    considered final: Spark only emits a `txn_window` group once no more late data is expected
    for it, matching the append-only Bronze sink in `streaming_io.write_bronze_stream`.
    """
    return (
        df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_path)
        .trigger(processingTime=f"{trigger_seconds} seconds")
        .start(path)
    )
