"""Bronze -> Silver cleansing rules: type conformance, dedup, PII tokenization, DQ checks."""

import hashlib

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

TRANSACTION_SCHEMA_COLUMNS = [
    "transaction_id",
    "account_id",
    "card_number",
    "merchant_id",
    "merchant_category",
    "amount",
    "currency",
    "transaction_ts",
    "channel",
    "device_id",
    "ip_address",
    "country_code",
]


def _tokenize(col_name: str) -> F.Column:
    """One-way SHA-256 tokenization for sensitive identifiers (card/account numbers)."""
    return F.sha2(F.col(col_name).cast("string"), 256)


def conform_types(df: DataFrame) -> DataFrame:
    return (
        df.withColumn("amount", F.col("amount").cast("decimal(18,2)"))
        .withColumn("transaction_ts", F.to_timestamp("transaction_ts"))
        .withColumn("transaction_date", F.to_date("transaction_ts"))
        .withColumn("country_code", F.upper(F.col("country_code")))
    )


def tokenize_pii(df: DataFrame) -> DataFrame:
    return df.withColumn("card_number_token", _tokenize("card_number")).drop("card_number")


def deduplicate_transactions(df: DataFrame) -> DataFrame:
    """Keep the most recently ingested record per transaction_id."""
    window = Window.partitionBy("transaction_id").orderBy(F.col("_ingested_at").desc())
    return (
        df.withColumn("_rn", F.row_number().over(window))
        .filter(F.col("_rn") == 1)
        .drop("_rn")
    )


def apply_data_quality_rules(df: DataFrame) -> DataFrame:
    """Quarantine-by-flag rather than silent drop, so downstream can audit rejects."""
    return df.withColumn(
        "_dq_passed",
        (F.col("amount").isNotNull())
        & (F.col("amount") > 0)
        & (F.col("transaction_id").isNotNull())
        & (F.col("account_id").isNotNull())
        & (F.length("country_code") == 2),
    )


def bronze_to_silver(df: DataFrame) -> DataFrame:
    df = conform_types(df)
    df = deduplicate_transactions(df)
    df = tokenize_pii(df)
    df = apply_data_quality_rules(df)
    return df
