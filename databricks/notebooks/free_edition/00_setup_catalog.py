# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Free Edition Setup
# MAGIC Creates the catalog/schema/volumes used by the Free Edition practice versions of
# MAGIC the medallion notebooks (`01`-`04` in this `free_edition/` folder). These notebooks
# MAGIC are functionally the same transformations as `databricks/notebooks/01-04`, but read
# MAGIC from a Unity Catalog **volume** (`/Volumes/...`) instead of an `abfss://` ADLS path,
# MAGIC since Free Edition doesn't support custom external storage locations.
# MAGIC
# MAGIC Run this once, then upload the synthetic data (see
# MAGIC `docs/free_edition_practice.md`) into the `raw` volume before running `01`.

# COMMAND ----------

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "fraud_platform")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

# COMMAND ----------

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")

for volume in ["raw", "curated"]:
    spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.{volume}")

print(f"Ready: {catalog}.{schema} with volumes 'raw' and 'curated'")
print(f"Upload sample_data/card-network/transactions.csv to /Volumes/{catalog}/{schema}/raw/card-network/")
print(f"Upload sample_data/merchant_risk_lookup.csv to /Volumes/{catalog}/{schema}/raw/merchant_risk_lookup/")
