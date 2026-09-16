# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Bronze Ingestion
# MAGIC Reads raw source-system files from ADLS Gen2 `raw/` (landed by ADF) and appends them,
# MAGIC schema-on-read, into append-only Bronze Delta tables with ingestion audit columns.

# COMMAND ----------

import sys

sys.path.append("/Workspace/Repos/fraud-platform/databricks/src")

from pyspark.sql import functions as F

from utils.adls_io import MedallionPaths, write_delta
from utils.spark_session import get_spark

dbutils.widgets.text("storage_account", "stfraudplatformdevabcde")
dbutils.widgets.text("run_date", "")
dbutils.widgets.text("source_systems", "core-banking,card-network,digital-channel")

storage_account = dbutils.widgets.get("storage_account")
source_systems = dbutils.widgets.get("source_systems").split(",")

spark = get_spark("bronze-ingestion")
paths = MedallionPaths(storage_account=storage_account)

# COMMAND ----------

for source_system in source_systems:
    raw_df = (
        spark.read.option("header", True)
        .option("inferSchema", True)
        .csv(paths.raw(source_system))
        .withColumn("_ingested_at", F.current_timestamp())
        .withColumn("_source_file", F.input_file_name())
        .withColumn("_source_system", F.lit(source_system))
    )

    bronze_path = paths.silver(f"bronze_{source_system.replace('-', '_')}")
    write_delta(raw_df, bronze_path, mode="append", partition_by=["_source_system"])

    print(f"Bronze ingested: {source_system} -> {bronze_path} ({raw_df.count()} rows)")

# COMMAND ----------

# MAGIC %md
# MAGIC Next: `02_silver_transformations.py` reads these Bronze tables, applies cleansing/DQ
# MAGIC rules, and writes conformed Silver Delta tables.
