# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Bronze Ingestion (Free Edition practice version)
# MAGIC Same logic as `databricks/notebooks/01_bronze_ingestion.py`, adapted to read from a
# MAGIC Unity Catalog **volume** path (`/Volumes/<catalog>/<schema>/raw/...`) instead of an
# MAGIC `abfss://` ADLS path — Free Edition doesn't support custom external storage
# MAGIC locations, so a UC volume stands in for the `raw/` ADLS container.
# MAGIC
# MAGIC Run `00_setup_catalog.py` first, and upload the CSV(s) from
# MAGIC `scripts/generate_synthetic_data.py` into the `raw` volume (see
# MAGIC `docs/free_edition_practice.md`) before running this.

# COMMAND ----------

import sys

sys.path.append("/Workspace/Repos/fraud-platform/databricks/src")

from pyspark.sql import functions as F

dbutils.widgets.text("catalog", "main")
dbutils.widgets.text("schema", "fraud_platform")

catalog = dbutils.widgets.get("catalog")
schema = dbutils.widgets.get("schema")

raw_volume = f"/Volumes/{catalog}/{schema}/raw"
curated_volume = f"/Volumes/{catalog}/{schema}/curated"

# COMMAND ----------

raw_df = (
    spark.read.option("header", True)
    .option("inferSchema", True)
    .csv(f"{raw_volume}/card-network")
    .withColumn("_ingested_at", F.current_timestamp())
    .withColumn("_source_file", F.input_file_name())
    .withColumn("_source_system", F.lit("card-network"))
)

bronze_table = f"{catalog}.{schema}.bronze_card_network"
(
    raw_df.write.format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(bronze_table)
)

print(f"Bronze ingested: {bronze_table} ({raw_df.count()} rows)")
display(spark.table(bronze_table).limit(10))

# COMMAND ----------

# MAGIC %md
# MAGIC Next: `02_silver_transformations.py` reads `bronze_card_network` and writes the
# MAGIC conformed `silver_transactions` managed table.
