import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "databricks" / "src"))

pyspark = pytest.importorskip("pyspark")

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from utils.streaming_io import (  # noqa: E402
    apply_late_arrival_watermark,
    card_auth_stream_schema,
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
