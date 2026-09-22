# Changelog

All notable changes to this project are documented here. Dates are the week the increment landed.

## [Unreleased]
- Planned: provision `drift_monitor_job_config.json` as an actually-scheduled Databricks job
  (currently config-only, same as `job_config.json`) once job deployment is wired into CI

## 2026-09-22 — Drift monitor now fails the job instead of only printing

- Added `raise_if_drifted` and a `DriftAlertError` exception to `ml/src/monitor_drift.py`: when
  `check_promotion_gate_drift` flags live degradation, the run now raises with
  `build_drift_alert_message`'s formatted body as the exception message instead of only printing
  it, so the Databricks job task exits non-zero and trips the job's own
  `email_notifications.on_failure` channel — closes the previously-planned on-call alert routing
  item
- Added `databricks/jobs/drift_monitor_job_config.json`: a single-node scheduled job config for
  `monitor_drift.py`, running daily after the main ETL job with `email_notifications.on_failure`
  routed to the same `data-eng-alerts@example.com` address as `job_config.json`
- Added `tests/test_model_drift.py` coverage for `raise_if_drifted` (raises with the alert body
  when drifted, no-ops otherwise) and an end-to-end `run_drift_check` → `raise_if_drifted` case

## 2026-09-21 — Live model-quality drift monitor
- Added `snowflake/ddl/05_create_fraud_outcomes.sql`: `MARTS.CONFIRMED_FRAUD_OUTCOMES` table for
  ground-truth fraud outcomes reconciled after the chargeback/dispute window closes, plus
  `VW_RECONCILED_SCORED_TRANSACTIONS`, a view joining it back against `FRAUD_RISK_SCORES` to the
  exact population the drift monitor scores against
- Added `ml/src/monitor_drift.py`: pulls the trailing reconciled window from that view
  (`load_reconciled_scores_from_snowflake`), recomputes live AUC-PR with the same
  `evaluate.py::evaluate_predictions` used at training time (`compute_live_auc_pr`, skipping
  silently below `MIN_RECONCILED_SAMPLES` to avoid a false alarm on a thin sample), and compares
  it back against `train.py`'s `PROMOTION_AUC_PR_THRESHOLD` promotion gate with a tolerance band
  (`check_promotion_gate_drift`) so live degradation is caught between scheduled retrains rather
  than only at the next training run; `build_drift_alert_message` formats the on-call-facing alert
  body, matching the ETL job's existing failure-alert tone; closes the previously-planned
  "model-quality drift monitor" item
- Added `tests/test_model_drift.py` covering the min-sample skip, both drifted/not-drifted branches
  of the gate comparison, the alert message contents, and the end-to-end `run_drift_check` flow
  (mocked Snowflake connector, no live warehouse required)

## 2026-09-19 — Databricks Model Serving endpoint for real-time inference
- Added `ml/src/serving.py`: deploys the registered `fraud-risk-classifier` model behind a
  Databricks Model Serving endpoint (`build_endpoint_config`, `deploy_serving_endpoint` —
  create-or-update against the current `Production` version, `wait_until_ready`) and a
  synchronous scoring helper (`build_scoring_payload`, `score_transaction`) for authorization-time
  calls, mirroring `inference.py::score_batch`'s batch path
- Added `databricks-sdk==0.28.0` to `requirements.txt`
- Updated `architecture.md`'s Machine Learning section to point at the now-deployed real-time
  path instead of describing it as documented-but-not-deployed
- Added `tests/test_serving.py` covering the endpoint config shape, scoring payload
  validation, and the create-vs-update deploy branch (mocked `WorkspaceClient`, no live
  workspace required)

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
