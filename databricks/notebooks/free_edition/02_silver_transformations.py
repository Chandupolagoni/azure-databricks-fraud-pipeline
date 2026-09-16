# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Silver Transformations (Free Edition practice version)
# MAGIC Reuses the exact cleansing logic from `databricks/src/transformations/cleansing.py`
# MAGIC (tokenization, dedup, DQ flags), reading/writing Unity Catalog managed tables
# MAGIC instead of ADLS Delta paths.

# COMMAND ----------

import sys

sys.path.append("/Workspace/Repos/fraud-platform/databricks/src")

from transformations.cleansing import bronze_to_silver

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "fraud_platform")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

bronze_df = spark.table(f"{catalog}.{schema}.bronze_card_network")
silver_df = bronze_to_silver(bronze_df)

passed = silver_df.filter("_dq_passed = true").drop("_dq_passed")
quarantined = silver_df.filter("_dq_passed = false")

print(f"Silver rows passing DQ: {passed.count()} | quarantined: {quarantined.count()}")

# COMMAND ----------

silver_table = f"{catalog}.{schema}.silver_transactions"
quarantine_table = f"{catalog}.{schema}.silver_transactions_quarantine"

if spark.catalog.tableExists(silver_table):
    from delta.tables import DeltaTable

    target = DeltaTable.forName(spark, silver_table)
    (
        target.alias("target")
        .merge(passed.alias("source"), "target.transaction_id = source.transaction_id")
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
else:
    passed.write.format("delta").saveAsTable(silver_table)

quarantined.write.format("delta").mode("append").option("mergeSchema", "true").saveAsTable(quarantine_table)

display(spark.table(silver_table).limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC Next: `03_gold_aggregations.py` and `04_feature_engineering.py` build on
# MAGIC `silver_transactions`.
