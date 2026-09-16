# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Fraud Feature Engineering
# MAGIC Builds the Gold `fraud_features` table consumed by `ml/src/train.py` and by the
# MAGIC batch scoring job (`ml/src/inference.py`).

# COMMAND ----------

import sys

sys.path.append("/Workspace/Repos/fraud-platform/databricks/src")

from utils.adls_io import MedallionPaths, write_delta
from utils.spark_session import get_spark
from transformations.fraud_features import build_fraud_feature_set

dbutils.widgets.text("storage_account", "stfraudplatformdevabcde")
storage_account = dbutils.widgets.get("storage_account")

spark = get_spark("fraud-feature-engineering")
paths = MedallionPaths(storage_account=storage_account)

# COMMAND ----------

silver_txns = spark.read.format("delta").load(paths.silver("transactions"))

# Precomputed merchant-category historical chargeback rate, refreshed weekly.
merchant_risk_lookup = spark.read.format("delta").load(paths.gold("merchant_risk_lookup"))

feature_df = build_fraud_feature_set(silver_txns, merchant_risk_lookup)

# COMMAND ----------

write_delta(
    feature_df,
    paths.gold("fraud_features"),
    mode="overwrite",
    partition_by=["transaction_date"],
)

print(f"fraud_features written: {feature_df.count()} rows")

# COMMAND ----------

# MAGIC %md
# MAGIC This table is the training/inference feature set for `ml/src/train.py` and the
# MAGIC source for the `RAW.FRAUD_FEATURES` external table loaded into Snowflake.
