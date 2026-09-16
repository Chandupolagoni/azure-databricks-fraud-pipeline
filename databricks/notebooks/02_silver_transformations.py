# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Silver Transformations
# MAGIC Cleanses, deduplicates, tokenizes PII, and applies data-quality rules on the Bronze
# MAGIC transaction table, producing the conformed Silver `transactions` Delta table.

# COMMAND ----------

import sys

sys.path.append("/Workspace/Repos/fraud-platform/databricks/src")

from utils.adls_io import MedallionPaths, upsert_delta
from utils.spark_session import get_spark
from transformations.cleansing import bronze_to_silver

dbutils.widgets.text("storage_account", "stfraudplatformdevabcde")
storage_account = dbutils.widgets.get("storage_account")

spark = get_spark("silver-transformations")
paths = MedallionPaths(storage_account=storage_account)

# COMMAND ----------

bronze_df = spark.read.format("delta").load(paths.silver("bronze_card_network"))
silver_df = bronze_to_silver(bronze_df)

passed = silver_df.filter("_dq_passed = true")
quarantined = silver_df.filter("_dq_passed = false")

print(f"Silver rows passing DQ: {passed.count()} | quarantined: {quarantined.count()}")

# COMMAND ----------

upsert_delta(
    passed.drop("_dq_passed"),
    paths.silver("transactions"),
    merge_keys=["transaction_id"],
    spark=spark,
)

quarantined.write.format("delta").mode("append").save(paths.silver("transactions_quarantine"))

# COMMAND ----------

# MAGIC %md
# MAGIC Next: `03_gold_aggregations.py` builds business aggregates, and
# MAGIC `04_feature_engineering.py` builds the fraud feature set on top of this Silver table.
