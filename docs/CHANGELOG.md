# Changelog

All notable changes to this project are documented here. Dates are the week the increment landed.

## [Unreleased]
- Planned: Databricks Model Serving endpoint wiring for real-time inference

## 2026-09-18 — Windowed fraud-velocity features on the streaming Bronze table
- Added `databricks/src/transformations/streaming_fraud_features.py`: sliding-window
  transaction count/sum/distinct-merchant-category aggregation per account
  (`add_windowed_velocity_features`), a spike-candidate flag on top of it
  (`add_velocity_spike_flag`), and a watermark-bounded append-mode Delta sink
  (`write_windowed_features_stream`)
- Added `databricks/notebooks/06_streaming_fraud_velocity_features.py`: reads the streaming
  Bronze card-authorization table from `05_streaming_card_auth_ingestion.py`, applies the same
  late-arrival watermark, and writes windowed velocity features directly on the stream instead
  of waiting for the next `04_feature_engineering.py` batch run; closes the previously-planned
  "windowed fraud-velocity features on the new streaming Bronze table" item
- Added `tests/test_streaming_fraud_features.py` covering the windowed aggregation and the
  spike-flag thresholds

## 2026-09-16 — Streaming card-authorization ingestion (prototype)
- Added `databricks/src/utils/streaming_io.py`: Auto Loader (`cloudFiles`) read helper with a
  pinned schema, a shared batch/streaming late-arrival watermark helper, and an append-only
  Delta streaming sink on a fixed `processingTime` trigger
- Added `databricks/notebooks/05_streaming_card_auth_ingestion.py`: near-real-time Bronze
  ingestion for card-network authorization events, landing within seconds instead of waiting
  for the next daily batch window; first slice of the previously-planned streaming ingestion
  path (windowed feature engineering on the stream is the next slice)
- Added `tests/test_streaming_io.py` covering the pinned stream schema and the watermark helper

## 2026-09-16 — Initial release
- Terraform modules: resource group, networking (VNet-injected Databricks), ADLS Gen2 (medallion containers), Key Vault, Databricks workspace + cluster policy, Azure Data Factory
- ADF pipelines: `pl_ingest_raw_transactions`, `pl_orchestrate_full_pipeline`, daily + event-based triggers
- Databricks: Bronze/Silver/Gold PySpark notebooks, reusable `src/` transformation + IO modules, job config
- Snowflake: RAW/STAGING/MARTS schemas, Snowpipe, Streams & Tasks, stored procedure for mart refresh
- ML: synthetic-data-capable training pipeline, MLflow tracking/registry integration, batch inference, model card
- CI/CD: GitHub Actions for lint/test and Terraform plan-on-PR
- Docs: architecture write-up, data dictionary, operations runbook
