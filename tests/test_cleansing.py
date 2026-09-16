import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "databricks" / "src"))

pyspark = pytest.importorskip("pyspark")

from pyspark.sql import SparkSession  # noqa: E402

from transformations.cleansing import (  # noqa: E402
    apply_data_quality_rules,
    conform_types,
    deduplicate_transactions,
    tokenize_pii,
)


@pytest.fixture(scope="module")
def spark():
    return (
        SparkSession.builder.master("local[2]")
        .appName("test-cleansing")
        .getOrCreate()
    )


def test_conform_types_casts_amount_and_date(spark):
    df = spark.createDataFrame(
        [("t1", "2024-01-01 10:00:00", "10.5", "us")],
        ["transaction_id", "transaction_ts", "amount", "country_code"],
    )
    out = conform_types(df).collect()[0]
    assert str(out["amount"]) == "10.50"
    assert out["country_code"] == "US"
    assert out["transaction_date"] is not None


def test_deduplicate_keeps_latest_ingested(spark):
    from pyspark.sql import functions as F

    df = spark.createDataFrame(
        [("t1", "2024-01-01T00:00:00"), ("t1", "2024-01-02T00:00:00")],
        ["transaction_id", "_ingested_at"],
    ).withColumn("_ingested_at", F.to_timestamp("_ingested_at"))

    result = deduplicate_transactions(df)
    assert result.count() == 1
    assert result.collect()[0]["_ingested_at"].isoformat().startswith("2024-01-02")


def test_tokenize_pii_removes_card_number(spark):
    df = spark.createDataFrame([("4111111111111111",)], ["card_number"])
    out = tokenize_pii(df)
    assert "card_number" not in out.columns
    assert "card_number_token" in out.columns
    assert len(out.collect()[0]["card_number_token"]) == 64  # sha256 hex length


def test_data_quality_flags_invalid_rows(spark):
    df = spark.createDataFrame(
        [
            ("t1", "a1", 10.0, "US"),
            ("t2", "a2", -5.0, "US"),
            (None, "a3", 10.0, "US"),
        ],
        ["transaction_id", "account_id", "amount", "country_code"],
    )
    out = apply_data_quality_rules(df).collect()
    results = {row["transaction_id"]: row["_dq_passed"] for row in out if row["transaction_id"]}
    assert results["t1"] is True
    assert results["t2"] is False
