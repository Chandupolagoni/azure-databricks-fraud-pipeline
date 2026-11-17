"""Silver -> Gold fraud-relevant feature engineering.

Features are designed to be computable in both batch (this module) and, with the same
window logic, a streaming context — a common ask in fraud platforms moving toward
near-real-time scoring.
"""

from pyspark.sql import DataFrame
from pyspark.sql import functions as F
from pyspark.sql.window import Window

# Trailing-window z-score threshold for flagging a single transaction's amount as an
# outlier for its own account (see add_amount_deviation_feature below).
OUTLIER_ZSCORE_THRESHOLD = 3.0


def add_transaction_velocity_features(df: DataFrame) -> DataFrame:
    """Count and sum of transactions per account over trailing 1h/24h windows."""
    account_window_1h = (
        Window.partitionBy("account_id")
        .orderBy(F.col("transaction_ts").cast("long"))
        .rangeBetween(-3600, 0)
    )
    account_window_24h = (
        Window.partitionBy("account_id")
        .orderBy(F.col("transaction_ts").cast("long"))
        .rangeBetween(-86400, 0)
    )

    return (
        df.withColumn("txn_count_1h", F.count("transaction_id").over(account_window_1h))
        .withColumn("txn_amount_sum_1h", F.sum("amount").over(account_window_1h))
        .withColumn("txn_count_24h", F.count("transaction_id").over(account_window_24h))
        .withColumn("txn_amount_sum_24h", F.sum("amount").over(account_window_24h))
    )


def add_geo_velocity_feature(df: DataFrame) -> DataFrame:
    """Flags an "impossible travel" pattern: country changes faster than plausible."""
    account_window = Window.partitionBy("account_id").orderBy("transaction_ts")

    return (
        df.withColumn("prev_country_code", F.lag("country_code").over(account_window))
        .withColumn("prev_transaction_ts", F.lag("transaction_ts").over(account_window))
        .withColumn(
            "minutes_since_prev_txn",
            (F.col("transaction_ts").cast("long") - F.col("prev_transaction_ts").cast("long")) / 60.0,
        )
        .withColumn(
            "is_country_mismatch",
            (F.col("prev_country_code").isNotNull())
            & (F.col("country_code") != F.col("prev_country_code")),
        )
        .withColumn(
            "is_impossible_travel",
            F.col("is_country_mismatch") & (F.col("minutes_since_prev_txn") < 60),
        )
    )


def add_device_reuse_feature(df: DataFrame) -> DataFrame:
    """Distinct accounts seen on the same device/IP in the trailing 24h — a shared-device signal."""
    device_window = (
        Window.partitionBy("device_id")
        .orderBy(F.col("transaction_ts").cast("long"))
        .rangeBetween(-86400, 0)
    )
    return df.withColumn(
        "distinct_accounts_per_device_24h",
        F.approx_count_distinct("account_id").over(device_window),
    )


def add_amount_deviation_feature(df: DataFrame) -> DataFrame:
    """Flags a transaction whose amount is a statistical outlier for its own account.

    The velocity features above (txn_count_*, txn_amount_sum_*) catch unusually *many* or
    unusually *large-in-aggregate* transactions over a window, but say nothing about a single
    transaction's size relative to that specific account's own spending pattern -- a $2,000
    purchase on an account that normally transacts in $20-$50 increments barely moves a 24h
    sum (it's one transaction), yet is exactly the kind of signal those windows miss. This
    computes a trailing 30-day per-account mean/stddev of `amount` and flags any transaction
    more than OUTLIER_ZSCORE_THRESHOLD standard deviations above it. Accounts with fewer than
    two prior transactions in the window (stddev undefined) are left unflagged rather than
    treated as an outlier by default.
    """
    account_window_30d = (
        Window.partitionBy("account_id")
        .orderBy(F.col("transaction_ts").cast("long"))
        .rangeBetween(-30 * 86400, 0)
    )

    return (
        df.withColumn("account_amount_mean_30d", F.avg("amount").over(account_window_30d))
        .withColumn("account_amount_stddev_30d", F.stddev("amount").over(account_window_30d))
        .withColumn(
            "amount_zscore_30d",
            F.when(
                F.col("account_amount_stddev_30d") > 0,
                (F.col("amount") - F.col("account_amount_mean_30d"))
                / F.col("account_amount_stddev_30d"),
            ).otherwise(F.lit(None).cast("double")),
        )
        .withColumn(
            "is_amount_outlier",
            F.coalesce(F.col("amount_zscore_30d") > OUTLIER_ZSCORE_THRESHOLD, F.lit(False)),
        )
    )


def add_merchant_risk_score(df: DataFrame, merchant_risk_lookup: DataFrame) -> DataFrame:
    """Joins a precomputed merchant-category risk score (chargeback rate historical avg)."""
    return df.join(merchant_risk_lookup, on="merchant_category", how="left").fillna(
        {"merchant_risk_score": 0.5}
    )


def build_fraud_feature_set(df: DataFrame, merchant_risk_lookup: DataFrame) -> DataFrame:
    df = add_transaction_velocity_features(df)
    df = add_geo_velocity_feature(df)
    df = add_device_reuse_feature(df)
    df = add_amount_deviation_feature(df)
    df = add_merchant_risk_score(df, merchant_risk_lookup)
    return df
