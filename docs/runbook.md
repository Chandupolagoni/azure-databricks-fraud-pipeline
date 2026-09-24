# Operations Runbook

## Initial deployment

1. **Terraform backend**: create a storage account/container for remote state before first `init` (`terraform init -backend-config=...`).
2. **Provision infrastructure**:
   ```bash
   cd terraform
   terraform init -backend-config=environments/dev.backend.hcl
   terraform plan -var-file=environments/dev.tfvars
   terraform apply -var-file=environments/dev.tfvars
   ```
3. **Populate Key Vault secrets** (out-of-band, not via Terraform state): Snowflake loader password, landing storage connection string, Databricks PAT for ADF's linked service.
4. **Databricks workspace bootstrap**:
   - Attach this repo via Databricks Repos (`/Repos/fraud-platform`)
   - Job deployment (`databricks/jobs/job_config.json` and `databricks/jobs/drift_monitor_job_config.json`) is handled by the
     `Deploy Databricks Jobs` GitHub Actions workflow on every push to `main` that touches either file
     (`scripts/deploy_databricks_jobs.py`, create-or-update via the Jobs API keyed on job name) — no manual `databricks jobs create` needed
     after the first `main` push that carries this bootstrap step; requires the `DATABRICKS_HOST`, `DATABRICKS_TOKEN`,
     `DATABRICKS_CLUSTER_POLICY_ID` and `DATABRICKS_STORAGE_ACCOUNT` repo secrets to be set first
   - Create the secret scope backed by Key Vault (`databricks secrets create-scope --scope fraud-platform-kv-scope --scope-backend-type AZURE_KEYVAULT ...`)
5. **Snowflake bootstrap** (run in order):
   ```bash
   snowsql -f snowflake/ddl/01_create_database_schema.sql
   snowsql -f snowflake/ddl/02_create_raw_tables.sql
   snowsql -f snowflake/ddl/03_create_curated_tables.sql
   snowsql -f snowflake/ddl/04_create_marts.sql
   snowsql -f snowflake/ddl/05_create_fraud_outcomes.sql
   snowsql -f snowflake/ddl/06_create_merchant_risk_view.sql
   snowsql -f snowflake/procedures/sp_load_fraud_marts.sql
   snowsql -f snowflake/snowpipe/pipe_transactions.sql
   snowsql -f snowflake/tasks/task_refresh_marts.sql
   ```
6. **ADF**: import `adf/pipelines`, `adf/datasets`, `adf/linkedServices`, `adf/triggers` via the ADF `Publish` workflow or `az datafactory` CLI; update the Snowflake/landing linked service connection strings to point at the real Key Vault secrets.
7. **Publish the daily trigger**: `az datafactory trigger start --trigger-name tr_daily_schedule ...`

## Daily operation

- `tr_daily_schedule` fires `pl_orchestrate_full_pipeline` at 05:00 UTC.
- On failure, `NotifyOnFailure` posts to the ops webhook; check the ADF pipeline run in the Azure portal for the failing activity, then the corresponding Databricks job run for stack traces.
- Snowpipe ingestion lag can be checked with `SELECT * FROM TABLE(INFORMATION_SCHEMA.PIPE_USAGE_HISTORY(...))`.
- Fraud-ops merchant review: `SELECT * FROM FRAUD_PLATFORM.MARTS.VW_MERCHANT_RISK_TRIAGE_QUEUE` lists merchants whose trailing 30-day flagged rate is `ELEVATED` or `HIGH`, worst first — this is the "merchants to review today" list. A merchant sitting at `HIGH` with a large `risk_score_divergence` (live rate far above `historical_risk_score`) is a candidate for an out-of-band `DIM_MERCHANT.merchant_risk_score` update ahead of the next offline recompute.

## Retraining the fraud model

```bash
cd ml/src
python train.py --delta-path abfss://curated@<account>.dfs.core.windows.net/gold/fraud_features \
                 --labels-path abfss://curated@<account>.dfs.core.windows.net/gold/fraud_labels
```

Review the MLflow run in the tracking UI; if `auc_pr` clears the gate the model auto-promotes to `Staging`. Manual review + `Production` promotion is done via the MLflow Model Registry UI or `MlflowClient.transition_model_version_stage`.

## Common incidents

| Symptom | Likely cause | First step |
|---|---|---|
| ADF copy activity failing on landing files | Source file schema drift | Check `LookupSourceFileManifest` output vs. `ds_landing_source_file` schema |
| Databricks job stuck / OOM | Skewed partition or undersized job cluster | Check Spark UI stage metrics; consider raising `autoscale.max_workers` in `job_config.json` |
| Snowpipe not ingesting new files | Event Grid notification integration misconfigured | `ALTER PIPE ... REFRESH` to manually backfill, then check the notification integration |
| `TASK_REFRESH_MARTS` not running | Task suspended or stream has no new data | `SHOW TASKS`, `SELECT SYSTEM$STREAM_HAS_DATA(...)` |
