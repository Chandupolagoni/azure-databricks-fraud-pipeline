# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Gold Aggregations
# MAGIC Business-level aggregates for BI/reporting: daily customer spend, merchant category
# MAGIC exposure. These land in Gold and are what gets loaded into Snowflake `MARTS`.

# COMMAND ----------

import sys

sys.path.append("/Workspace/Repos/fraud-platform/databricks/src")

from pyspark.sql import functions as F

from utils.adls_io import MedallionPaths, write_delta
from utils.spark_session import get_spark

dbutils.widgets.text("storage_account", "stfraudplatformdevabcde")
storage_account = dbutils.widgets.get("storage_account")

spark = get_spark("gold-aggregations")
paths = MedallionPaths(storage_account=storage_account)

# COMMAND ----------

silver_txns = spark.read.format("delta").load(paths.silver("transactions"))

daily_customer_spend = silver_txns.groupBy("account_id", "transaction_date").agg(
    F.sum("amount").alias("total_spend"),
    F.count("transaction_id").alias("txn_count"),
    F.countDistinct("merchant_id").alias("distinct_merchants"),
)

merchant_category_exposure = silver_txns.groupBy(
    "merchant_category", "transaction_date"
).agg(
    F.sum("amount").alias("total_volume"),
    F.count("transaction_id").alias("txn_count"),
    F.countDistinct("account_id").alias("distinct_customers"),
)

# COMMAND ----------

write_delta(
    daily_customer_spend,
    paths.gold("daily_customer_spend"),
    mode="overwrite",
    partition_by=["transaction_date"],
)
write_delta(
    merchant_category_exposure,
    paths.gold("merchant_category_exposure"),
    mode="overwrite",
    partition_by=["transaction_date"],
)

print("Gold aggregates written: daily_customer_spend, merchant_category_exposure")
