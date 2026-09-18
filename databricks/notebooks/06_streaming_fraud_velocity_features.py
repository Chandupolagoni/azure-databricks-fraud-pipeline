# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Streaming Fraud-Velocity Features
# MAGIC Second slice of the streaming ingestion path started in `05_streaming_card_auth_ingestion.py`:
# MAGIC reads the streaming Bronze card-authorization table and computes windowed
# MAGIC transaction-velocity features (`transformations.streaming_fraud_features`) directly on the
# MAGIC stream, instead of waiting for the next `04_feature_engineering.py` batch run.
# MAGIC
# MAGIC This closes the `[Unreleased]` "windowed fraud-velocity features ... on the new streaming
# MAGIC Bronze table" item in `docs/CHANGELOG.md`. Model Serving wiring (the other `[Unreleased]`
# MAGIC item) is still the next slice.
# MAGIC
# MAGIC Run as its own Databricks Job the same way as `05_streaming_card_auth_ingestion.py` — this
# MAGIC notebook does not terminate on its own (`awaitTermination` blocks until the job is stopped
# MAGIC or hits `max_run_seconds`).

# COMMAND ----------

import sys

sys.path.append("/Workspace/Repos/fraud-platform/databricks/src")

from transformations.streaming_fraud_features import (
    add_velocity_spike_flag,
    add_windowed_velocity_features,
    write_windowed_features_stream,
)
from utils.adls_io import MedallionPaths
from utils.spark_session import get_spark
from utils.streaming_io import apply_late_arrival_watermark

dbutils.widgets.text("storage_account", "stfraudplatformdevabcde")
dbutils.widgets.text("window_duration", "5 minutes")
dbutils.widgets.text("slide_duration", "1 minute")
dbutils.widgets.text("trigger_seconds", "30")
dbutils.widgets.text("max_run_seconds", "")  # blank = run until manually stopped

storage_account = dbutils.widgets.get("storage_account")
window_duration = dbutils.widgets.get("window_duration")
slide_duration = dbutils.widgets.get("slide_duration")
trigger_seconds = int(dbutils.widgets.get("trigger_seconds"))
max_run_seconds = dbutils.widgets.get("max_run_seconds")

spark = get_spark("streaming-fraud-velocity-features")
paths = MedallionPaths(storage_account=storage_account)

# COMMAND ----------

bronze_stream = spark.readStream.format("delta").load(paths.silver("bronze_card_network_stream"))
watermarked_stream = apply_late_arrival_watermark(bronze_stream, delay_threshold="15 minutes")

windowed_features = add_windowed_velocity_features(
    watermarked_stream, window_duration=window_duration, slide_duration=slide_duration
)
flagged_features = add_velocity_spike_flag(windowed_features)

output_path = paths.silver("card_auth_velocity_features_stream")
checkpoint_path = paths.checkpoint("card_auth_velocity_features_stream")

query = write_windowed_features_stream(
    flagged_features,
    path=output_path,
    checkpoint_path=checkpoint_path,
    trigger_seconds=trigger_seconds,
)

print(f"Streaming query '{query.name or query.id}' started -> {output_path}")
print(f"Checkpoint: {checkpoint_path}")

# COMMAND ----------

# MAGIC %md
# MAGIC `max_run_seconds` mirrors `05_streaming_card_auth_ingestion.py`: set only for scheduled
# MAGIC smoke-test runs that validate the job still starts cleanly, and leave it blank for the
# MAGIC long-running `prod` job.

if max_run_seconds:
    query.awaitTermination(timeout=int(max_run_seconds))
    query.stop()
else:
    query.awaitTermination()
