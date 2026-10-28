import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "databricks" / "src"))

pyspark = pytest.importorskip("pyspark")

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402
from pyspark.sql.types import StringType, StructField, StructType  # noqa: E402

from utils.streaming_io import (  # noqa: E402
    RESCUED_DATA_COLUMN,
    apply_late_arrival_watermark,
    card_auth_stream_schema,
    split_streaming_quality,
)


@pytest.fixture(scope="module")
def spark():
    return SparkSession.builder.master("local[2]").appName("test-streaming-io").getOrCreate()


def test_card_auth_stream_schema_has_expected_fields():
    schema = card_auth_stream_schema()
    field_names = [f.name for f in schema.fields]

    assert field_names == [
        "transaction_id",
        "account_id",
        "device_id",
        "merchant_category",
        "country_code",
        "amount",
        "transaction_ts",
    ]
    assert not schema["transaction_id"].nullable
    assert not schema["transaction_ts"].nullable


def test_apply_late_arrival_watermark_preserves_rows_and_columns(spark):
    df = spark.createDataFrame(
        [("t1", "2024-01-01 10:00:00")],
        ["transaction_id", "transaction_ts"],
    ).withColumn("transaction_ts", F.to_timestamp("transaction_ts"))

    watermarked = apply_late_arrival_watermark(df, delay_threshold="10 minutes")

    assert watermarked.columns == df.columns
    assert watermarked.count() == 1


def test_split_streaming_quality_separates_rescued_rows(spark):
    df = spark.createDataFrame(
        [
            ("t1", "2024-01-01 10:00:00", None),
            ("t2", "2024-01-01 10:05:00", '{"extra_field": "unexpected"}'),
        ],
        ["transaction_id", "transaction_ts", RESCUED_DATA_COLUMN],
    ).withColumn("transaction_ts", F.to_timestamp("transaction_ts"))

    clean, quarantined = split_streaming_quality(df)

    assert clean.count() == 1
    assert clean.collect()[0]["transaction_id"] == "t1"
    assert RESCUED_DATA_COLUMN not in clean.columns

    assert quarantined.count() == 1
    assert quarantined.collect()[0]["transaction_id"] == "t2"
    assert RESCUED_DATA_COLUMN in quarantined.columns


def test_split_streaming_quality_all_clean_when_nothing_rescued(spark):
    schema = StructType(
        [
            StructField("transaction_id", StringType(), nullable=False),
            StructField(RESCUED_DATA_COLUMN, StringType(), nullable=True),
        ]
    )
    df = spark.createDataFrame([("t1", None)], schema)

    clean, quarantined = split_streaming_quality(df)

    assert clean.count() == 1
    assert quarantined.count() == 0

