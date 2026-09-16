# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Streaming Card-Authorization Ingestion (prototype)
# MAGIC Near-real-time counterpart to `01_bronze_ingestion.py`: an Auto Loader
# MAGIC (`cloudFiles`) Structured Streaming job that lands card-network authorization
# MAGIC events into a streaming Bronze Delta table within seconds of arrival, instead
# MAGIC of waiting for the next daily batch window.
# MAGIC
# MAGIC This is the first slice of the `[Unreleased]` "streaming ingestion path"
# MAGIC item in `docs/CHANGELOG.md`. It only covers Bronze; windowed velocity
# MAGIC features (`fraud_features.add_transaction_velocity_features`) are batch-only
# MAGIC today and are the natural next slice once this stream is stable in `dev`.
# MAGIC
# MAGIC Run as a Databricks Job with `Continuous` or a long-running `All-purpose`
# MAGIC cluster — this notebook does not terminate on its own (`awaitTermination`
# MAGIC blocks until the job is stopped or hits `max_run_seconds`).

# COMMAND ----------

import sys

sys.path.append("/Workspace/Repos/fraud-platform/databricks/src")

from utils.adls_io import MedallionPaths
from utils.spark_session import get_spark
from utils.streaming_io import (
    apply_late_arrival_watermark,
    read_card_auth_stream,
    write_bronze_stream,
)

dbutils.widgets.text("storage_account", "stfraudplatformdevabcde")
dbutils.widgets.text("trigger_seconds", "30")
dbutils.widgets.text("max_run_seconds", "")  # blank = run until manually stopped

storage_account = dbutils.widgets.get("storage_account")
trigger_seconds = int(dbutils.widgets.get("trigger_seconds"))
max_run_seconds = dbutils.widgets.get("max_run_seconds")

spark = get_spark("streaming-card-auth-ingestion")
paths = MedallionPaths(storage_account=storage_account)

# COMMAND ----------

raw_stream = read_card_auth_stream(spark, paths)
watermarked_stream = apply_late_arrival_watermark(raw_stream, delay_threshold="15 minutes")

bronze_path = paths.silver("bronze_card_network_stream")
checkpoint_path = paths.checkpoint("bronze_card_network_stream")

query = write_bronze_stream(
    watermarked_stream,
    path=bronze_path,
    checkpoint_path=checkpoint_path,
    trigger_seconds=trigger_seconds,
)

print(f"Streaming query '{query.name or query.id}' started -> {bronze_path}")
print(f"Checkpoint: {checkpoint_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC `max_run_seconds` is set only for scheduled smoke-test runs (a Job that
# MAGIC validates the stream still starts cleanly against `dev` sample data and then
# MAGIC exits); leave it blank for the long-running `prod` job.

if max_run_seconds:
    query.awaitTermination(timeout=int(max_run_seconds))
    query.stop()
else:
    query.awaitTermination()
