# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Gold Aggregations (Free Edition practice version)
# MAGIC Same aggregates as `databricks/notebooks/03_gold_aggregations.py`, written to
# MAGIC Unity Catalog managed tables.

# COMMAND ----------

from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "fraud_platform")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

silver_txns = spark.table(f"{catalog}.{schema}.silver_transactions")

daily_customer_spend = silver_txns.groupBy("account_id", "transaction_date").agg(
    F.sum("amount").alias("total_spend"),
    F.count("transaction_id").alias("txn_count"),
    F.countDistinct("merchant_id").alias("distinct_merchants"),
)

merchant_category_exposure = silver_txns.groupBy("merchant_category", "transaction_date").agg(
    F.sum("amount").alias("total_volume"),
    F.count("transaction_id").alias("txn_count"),
    F.countDistinct("account_id").alias("distinct_customers"),
)

# COMMAND ----------

daily_customer_spend.write.format("delta").mode("overwrite").option(
    "overwriteSchema", "true"
).saveAsTable(f"{catalog}.{schema}.gold_daily_customer_spend")

merchant_category_exposure.write.format("delta").mode("overwrite").option(
    "overwriteSchema", "true"
).saveAsTable(f"{catalog}.{schema}.gold_merchant_category_exposure")

print("Gold aggregates written: gold_daily_customer_spend, gold_merchant_category_exposure")
display(spark.table(f"{catalog}.{schema}.gold_merchant_category_exposure").orderBy(F.desc("total_volume")).limit(10))
