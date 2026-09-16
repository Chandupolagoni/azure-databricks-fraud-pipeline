import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "databricks" / "src"))

pyspark = pytest.importorskip("pyspark")

from pyspark.sql import SparkSession  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

from transformations.fraud_features import (  # noqa: E402
    add_device_reuse_feature,
    add_geo_velocity_feature,
    add_merchant_risk_score,
)


@pytest.fixture(scope="module")
def spark():
    return SparkSession.builder.master("local[2]").appName("test-fraud-features").getOrCreate()


def test_geo_velocity_flags_impossible_travel(spark):
    df = spark.createDataFrame(
        [
            ("a1", "t1", "2024-01-01 10:00:00", "US"),
            ("a1", "t2", "2024-01-01 10:05:00", "FR"),  # 5 min later, different country
        ],
        ["account_id", "transaction_id", "transaction_ts", "country_code"],
    ).withColumn("transaction_ts", F.to_timestamp("transaction_ts"))

    out = {row["transaction_id"]: row for row in add_geo_velocity_feature(df).collect()}
    assert out["t2"]["is_impossible_travel"] is True
    assert out["t1"]["is_impossible_travel"] is False


def test_device_reuse_counts_distinct_accounts(spark):
    df = spark.createDataFrame(
        [
            ("d1", "a1", "2024-01-01 00:00:00"),
            ("d1", "a2", "2024-01-01 01:00:00"),
            ("d1", "a3", "2024-01-01 02:00:00"),
        ],
        ["device_id", "account_id", "transaction_ts"],
    ).withColumn("transaction_ts", F.to_timestamp("transaction_ts"))

    out = add_device_reuse_feature(df).orderBy("transaction_ts").collect()
    assert out[-1]["distinct_accounts_per_device_24h"] >= 2


def test_merchant_risk_score_fills_default_when_missing(spark):
    txns = spark.createDataFrame([("m_unknown",)], ["merchant_category"])
    lookup = spark.createDataFrame([("m_known", 0.9)], ["merchant_category", "merchant_risk_score"])

    out = add_merchant_risk_score(txns, lookup).collect()[0]
    assert out["merchant_risk_score"] == 0.5
