# Changelog

All notable changes to this project are documented here. Dates are the week the increment landed.

## [Unreleased]

## 2026-10-06 — Account-level velocity watchlist for fraud-ops

- Added `snowflake/ddl/08_create_account_velocity_watchlist.sql`: `VW_ACCOUNT_VELOCITY_WATCHLIST`
  joins the static, offline-recomputed `DIM_CUSTOMER.risk_segment` against a rolling
  trailing-7-day flagged rate and transaction velocity from `FCT_TRANSACTIONS`/`FRAUD_RISK_SCORES`
  — the account-side counterpart to `VW_MERCHANT_RISK_SUMMARY` (06_create_merchant_risk_view.sql),
  which only ever covered the merchant side. A shorter 7-day window is used here than the
  merchant view's 30-day one since account-level fraud bursts play out over days, not weeks.
  `VW_ACCOUNT_VELOCITY_TRIAGE_QUEUE` filters to `ELEVATED`/`HIGH` `velocity_tier`, sorted
  worst-first with `distinct_merchants_7d` as a tiebreaker so a card-testing-style account
  hitting many merchants in the window surfaces ahead of one concentrated at a single merchant
- Updated `docs/data_dictionary.md` with the new view's columns
- Updated `docs/runbook.md`'s Daily operation section with a "fraud-ops account review" note
  mirroring the existing merchant triage queue note, and added a Common incidents row for a
  thin/empty triage queue caused by `TASK_REFRESH_FRAUD_SCORES` lag rather than low volume

## 2026-09-30 — Silver quarantine-rate monitor now fails the job instead of only printing counts

- Added `databricks/src/transformations/data_quality_monitor.py`: `compute_quarantine_rate`
  and `check_quarantine_rate_threshold` turn the `passed`/`quarantined` row counts
  `02_silver_transformations.py` already printed into a real signal — flags once the
  quarantine rate clears `QUARANTINE_RATE_THRESHOLD` (2%) on a batch of at least
  `MIN_ROWS_FOR_CHECK` (100) rows, skipping thin batches the same way
  `monitor_drift.py::MIN_RECONCILED_SAMPLES` skips thin reconciliation windows; a new
  `DataQualityAlertError` + `raise_if_quarantine_rate_breached` fails the run with a
  formatted alert body (`build_dq_alert_message`) so the `silver_transformations` task
  exits non-zero and trips `job_config.json`'s existing `email_notifications.on_failure`
  channel, instead of a bad batch only ever showing up as a line in the job's logs
- Wired the check into `02_silver_transformations.py` right after the existing
  passed/quarantined count printout, and before the quarantine table write
- Added `tests/test_data_quality_monitor.py` covering the rate calculation (including the
  empty-batch zero-division guard), the threshold check's breach/no-breach branches, the
  thin-batch skip even when the rate itself is high, the alert message contents, and both
  branches of `raise_if_quarantine_rate_breached`
- Added a `Common incidents` row to `docs/runbook.md` for the new `DataQualityAlertError`
  failure mode, pointing on-call at `transactions_quarantine` to find the failing rule(s)

## 2026-09-29 — Blob-service audit logging for the ADLS storage account

- Added `terraform/modules/monitoring`: a `azurerm_log_analytics_workspace` plus an
  `azurerm_monitor_diagnostic_setting` on the ADLS storage account's `blobServices/default`,
  shipping `StorageRead`/`StorageWrite`/`StorageDelete` logs and `Transaction` metrics —
  closes a gap where `architecture.md`'s Storage section described firewall/private-endpoint
  access *restrictions* but nothing produced a queryable audit trail of what was actually
  read, written, or deleted, which financial-services data handling requires alongside
  access control
- Wired the new module into `terraform/main.tf` (`module.monitoring`, fed
  `module.storage.storage_account_id`), added `log_analytics_retention_days` to
  `terraform/variables.tf` (default 90) and a `log_analytics_workspace_id` output to
  `terraform/outputs.tf`
- Set environment-specific retention in `dev.tfvars` (30 days — dev doesn't need a long
  audit trail) and `prod.tfvars` (365 days — matches the raw zone's financial-services
  data-handling requirements already reflected in the lifecycle policy)
- Updated `architecture/architecture.md`'s Storage section, IaC section, and design
  decisions, and `docs/runbook.md` with a deployment verification step, a Daily operation
  note on querying `StorageBlobLogs`, and a Common incidents row for a missing diagnostic
  setting


## 2026-09-28 — Direct unit tests for the synthetic data generator

- Added `tests/test_generate_synthetic_data.py`: the first direct tests for
  `scripts/generate_synthetic_data.py`, covering the raw transaction schema shape (field
  order, card-number format, positive amounts, `acct_`/`dev_` id prefixes), that a given
  `--seed` reproduces every field except `transaction_id` (a fresh `uuid4` on each call, by
  design, so it's excluded from the determinism check rather than left to fail intermittently),
  that different seeds vary the generated account sequence, that each `merchant_id` keeps a
  single stable `merchant_category` across the run, that the returned category list has no
  duplicates and matches what the rows actually used, and that `write_csv` creates missing
  parent directories and round-trips row count and content correctly
- Closes the gap where the Free Edition practice path
  (`docs/free_edition_practice.md`) depended on this script's output matching the raw
  transaction schema, but nothing verified that contract automatically

## 2026-09-27 — ADLS lifecycle management policy for raw zone and checkpoints

- Added `azurerm_storage_management_policy` to `terraform/modules/storage/main.tf`: tiers
  `raw/` zone blobs Hot → Cool (`raw_zone_cool_tier_after_days`, default 30) → Archive
  (`raw_zone_archive_after_days`, default 90) as they age past the initial Bronze ingestion
  window instead of paying Hot-tier rates indefinitely for immutable, rarely-read historical
  data, and deletes stale `checkpoints/` blobs outright (`checkpoints_delete_after_days`,
  default 14) since Structured Streaming checkpoints are transient operational state with no
  business retention requirement; `curated/` (Silver + Gold) is intentionally left off the
  policy since it's actively queried by Databricks jobs, Snowflake external tables, and
  ad-hoc analysis
- Wired the three new variables through `terraform/variables.tf` and `terraform/main.tf`,
  and set environment-specific values in `dev.tfvars` (14/30/7 days — dev data churns fast
  and isn't retained for compliance) and `prod.tfvars` (30/90/14 days — matches the raw
  zone's financial-services data-handling requirements)
- Added `lifecycle_management_policy_id` output to the storage module
- Updated `architecture/architecture.md`'s Storage section and `docs/runbook.md` (a Daily
  operation note plus a Common incidents row for finding raw-zone files already tiered down)

## 2026-09-26 — Input validation and direct unit tests for evaluate_predictions

- Hardened `ml/src/evaluate.py::evaluate_predictions` — the metric function shared by
  `train.py`'s promotion gate and `monitor_drift.py`'s live drift check — to raise a clear
  `ValueError` on an empty `y_true`/`y_proba`, a length mismatch between the two, or a
  `decision_threshold` outside `[0.0, 1.0]`, instead of letting a malformed upstream result
  (a bad train/test split, a reconciled Snowflake window that came back misaligned) surface
  as an opaque `sklearn`/`numpy` broadcast error several frames deeper
- Added `tests/test_evaluate.py`: the function's first direct unit tests, covering a perfect
  classifier, an all-below-threshold case (zero precision/recall without dividing by zero),
  threshold sensitivity, the plain-Python-float return contract, and the three new validation
  errors — closes a gap where `evaluate_predictions` was only ever exercised indirectly through
  `test_model_drift.py`'s mocked drift-check flow

## 2026-09-25 — Chargeback reconciliation feed populates CONFIRMED_FRAUD_OUTCOMES

- Added `snowflake/ddl/07_create_chargeback_outcomes_feed.sql`: `RAW.RAW_CHARGEBACK_OUTCOMES`
  table plus a `STG_RAW_CHARGEBACKS` external stage over a new `raw/chargebacks/` landing path,
  and `STAGING.STRM_RAW_CHARGEBACK_OUTCOMES` (append-only stream, resolved disputes only)
- Added `snowflake/snowpipe/pipe_chargeback_outcomes.sql`: `PIPE_RAW_CHARGEBACK_OUTCOMES`,
  auto-ingesting network settlement files via the existing `ADLS_EVENT_GRID_INT` notification
  integration, mirroring `pipe_transactions.sql`'s split from its RAW table DDL
- Added `snowflake/procedures/sp_reconcile_fraud_outcomes.sql`: `SP_RECONCILE_FRAUD_OUTCOMES`
  merges the latest resolved outcome per transaction from the stream into
  `MARTS.CONFIRMED_FRAUD_OUTCOMES` (issuer-confirmed fraud flag, `'chargeback:<network>'`
  outcome source), joined against `FCT_TRANSACTIONS` so an outcome for a not-yet-ingested
  transaction is skipped and picked up on a later run instead of erroring on the FK
- Added `snowflake/tasks/task_reconcile_fraud_outcomes.sql`: `TASK_RECONCILE_FRAUD_OUTCOMES`,
  stream-triggered with a daily 06:30 UTC schedule as a safety net, matching
  `TASK_REFRESH_MARTS`'s pattern — closes the gap where `05_create_fraud_outcomes.sql`'s
  `CONFIRMED_FRAUD_OUTCOMES` table existed (feeding `ml/src/monitor_drift.py`'s live drift
  check) but nothing had ever populated it
- Updated `docs/runbook.md`'s Snowflake bootstrap sequence with the new DDL/procedure/pipe/task
  files, added a Daily operation note on the reconciliation cadence, and a Common incidents row
  for a stalled `TASK_RECONCILE_FRAUD_OUTCOMES`
- Updated `docs/data_dictionary.md` with column definitions for `RAW_CHARGEBACK_OUTCOMES` and
  `CONFIRMED_FRAUD_OUTCOMES`

## 2026-09-24 — Merchant risk triage view for fraud-ops

- Added `snowflake/ddl/06_create_merchant_risk_view.sql`: `MARTS.VW_MERCHANT_RISK_SUMMARY`
  joins the static, offline-recomputed `DIM_MERCHANT.merchant_risk_score` against a rolling
  trailing-30-day flagged rate from `FCT_TRANSACTIONS`/`FRAUD_RISK_SCORES`, plus a
  `risk_score_divergence` column (live rate minus historical score) and a `risk_tier`
  bucket (`INSUFFICIENT_VOLUME` / `NORMAL` / `ELEVATED` / `HIGH`) so fraud-ops can spot a
  merchant trending hot before the next offline score recompute catches up to it
- Added `MARTS.VW_MERCHANT_RISK_TRIAGE_QUEUE` on top of it — `ELEVATED`/`HIGH` merchants only,
  worst flagged rate first — as the day's merchant review list
- Updated `docs/runbook.md`'s Snowflake bootstrap sequence to include the new DDL file, and
  added a Daily operation note pointing fraud-ops at the triage queue query
- Updated `docs/data_dictionary.md` with column definitions for both new views

## 2026-09-23 — Wire Databricks job deployment into CI

- Added `scripts/deploy_databricks_jobs.py`: reads every job config JSON under `databricks/jobs/`
  (`job_config.json`, `drift_monitor_job_config.json`), substitutes their `{{cluster_policy_id}}`
  / `{{storage_account}}` template placeholders from env vars (`render_job_config`), and
  create-or-updates each job via the Databricks Jobs API keyed on job name (`find_existing_job_id`
  + `deploy_job` — `jobs/create` if the name isn't found, `jobs/reset` in place if it is), so
  re-running on every push to `main` updates existing jobs instead of creating duplicates
- Added `.github/workflows/deploy-databricks-jobs.yml`: runs the new script on push to `main`
  when either a job config or the script itself changes, using `DATABRICKS_HOST`,
  `DATABRICKS_TOKEN`, `DATABRICKS_CLUSTER_POLICY_ID` and `DATABRICKS_STORAGE_ACCOUNT` repo
  secrets — closes the "provision `drift_monitor_job_config.json` as an actually-scheduled job
  once job deployment is wired into CI" item that had been sitting under Unreleased
- Added `requests==2.32.3` to `requirements.txt` (direct dependency of the new deploy script)
- Updated `docs/runbook.md`'s "Databricks workspace bootstrap" step to point at the new CI-driven
  deployment instead of the old manual `databricks jobs create --json-file ...` step
- Added `tests/test_deploy_databricks_jobs.py` covering placeholder substitution (including the
  missing-env-var error and the no-placeholder no-op case), job lookup by exact name match, and
  the create-vs-reset branch of `deploy_job` (mocked `requests`, no live workspace required)

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
