# Changelog

All notable changes to this project are documented here. Dates are the week the increment landed.

## [Unreleased]
- Planned: streaming (Structured Streaming) ingestion path for near-real-time card-authorization scoring
- Planned: Databricks Model Serving endpoint wiring for real-time inference

## 2026-09-16 — Initial release
- Terraform modules: resource group, networking (VNet-injected Databricks), ADLS Gen2 (medallion containers), Key Vault, Databricks workspace + cluster policy, Azure Data Factory
- ADF pipelines: `pl_ingest_raw_transactions`, `pl_orchestrate_full_pipeline`, daily + event-based triggers
- Databricks: Bronze/Silver/Gold PySpark notebooks, reusable `src/` transformation + IO modules, job config
- Snowflake: RAW/STAGING/MARTS schemas, Snowpipe, Streams & Tasks, stored procedure for mart refresh
- ML: synthetic-data-capable training pipeline, MLflow tracking/registry integration, batch inference, model card
- CI/CD: GitHub Actions for lint/test and Terraform plan-on-PR
- Docs: architecture write-up, data dictionary, operations runbook
