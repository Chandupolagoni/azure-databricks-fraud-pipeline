"""Structured Streaming helpers for near-real-time card-authorization ingestion.

These mirror the batch helpers in `adls_io.py` but target the Auto Loader
(`cloudFiles`) source landing in the `raw/card-network` zone, so the same
Bronze contract (ingestion audit columns, append-only Delta) holds whether a
source system is ingested in batch or streamed.
"""

from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F
from pyspark.sql.streaming import StreamingQuery
from pyspark.sql.types import (
    DoubleType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

from utils.adls_io import MedallionPaths


def card_auth_stream_schema() -> StructType:
    """Explicit schema for streamed card-authorization events.

    Auto Loader can infer schema, but an explicit schema avoids a rescan of the
    landing zone on every stream (re)start and keeps failures at read time
    instead of surfacing downstream as null columns.
    """
    return StructType(
        [
            StructField("transaction_id", StringType(), nullable=False),
            StructField("account_id", StringType(), nullable=False),
            StructField("device_id", StringType(), nullable=True),
            StructField("merchant_category", StringType(), nullable=True),
            StructField("country_code", StringType(), nullable=True),
            StructField("amount", DoubleType(), nullable=True),
            StructField("transaction_ts", TimestampType(), nullable=False),
        ]
    )


def read_card_auth_stream(spark: SparkSession, paths: MedallionPaths) -> DataFrame:
    """Auto Loader stream over the `card-network` landing path, schema-on-read pinned."""
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "json")
        .option("cloudFiles.schemaLocation", paths.checkpoint("card_auth_schema"))
        .schema(card_auth_stream_schema())
        .load(paths.raw("card-network-stream"))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_system", F.lit("card-network"))
    )


def apply_late_arrival_watermark(
    df: DataFrame,
    event_time_col: str = "transaction_ts",
    delay_threshold: str = "15 minutes",
) -> DataFrame:
    """Bounds how long the engine keeps state for late-arriving authorizations.

    Shared with batch callers too: `withWatermark` is a no-op on a static
    DataFrame, so feature code that windows on `transaction_ts` can call this
    unconditionally regardless of whether it runs in the stream or a backfill.
    """
    return df.withWatermark(event_time_col, delay_threshold)


def write_bronze_stream(
    df: DataFrame,
    path: str,
    checkpoint_path: str,
    trigger_seconds: int = 30,
) -> StreamingQuery:
    """Starts an append-only micro-batch write of the streaming Bronze table.

    A fixed `processingTime` trigger (rather than `availableNow` or continuous
    mode) keeps this a genuine near-real-time job: small, frequent batches
    instead of one-shot or unsupported continuous processing.
    """
    return (
        df.writeStream.format("delta")
        .outputMode("append")
        .option("checkpointLocation", checkpoint_path)
        .trigger(processingTime=f"{trigger_seconds} seconds")
        .start(path)
    )
