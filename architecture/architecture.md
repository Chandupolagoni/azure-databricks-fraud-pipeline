# Architecture

## Overview

A medallion-architecture data platform on Azure for a financial services fraud & risk analytics use case, with Snowflake as the governed serving warehouse and an MLflow-tracked fraud model closing the loop.

## Components

### 1. Ingestion — Azure Data Factory
- `pl_ingest_raw_transactions`: copies core-banking, card-network, and digital-channel event files (batch, CSV/JSON/Parquet) from source (SFTP/Blob landing zone) into ADLS Gen2 `raw/` zone, partitioned by `ingest_date`.
- `pl_orchestrate_full_pipeline`: parent pipeline that triggers ingestion, then invokes the Databricks Jobs (Bronze→Silver→Gold) via the Databricks linked service, then triggers the Snowflake load task.
- Triggers: daily schedule trigger for batch loads; event-based trigger (Storage Event) for near-real-time card-authorization files.

### 2. Storage — ADLS Gen2
Hierarchical namespace with three logical zones inside one storage account, isolated by container/ACL:
- `raw/` — immutable landing zone, source-format
- `curated/` — Delta Lake tables, Silver + Gold
- `checkpoints/` — Structured Streaming / job checkpoints

Private endpoints + service endpoints restrict access to the VNet; a firewall rule set default-denies public network access, consistent with financial-services data handling requirements.

### 3. Transformation — Azure Databricks (PySpark + Delta Lake)
- **Bronze**: schema-on-read ingestion of raw files into append-only Delta tables, with `_ingested_at`, `_source_file` audit columns.
- **Silver**: type conformance, null/duplicate handling, PII tokenization of account/card numbers, data-quality assertions (`databricks/src/transformations/cleansing.py`).
- **Gold**: business aggregates (daily customer spend, merchant category exposure) and fraud-specific features — transaction velocity, geo-distance-since-last-transaction, device/IP reuse, merchant risk score (`databricks/src/transformations/fraud_features.py`).
- Jobs are defined declaratively in `databricks/jobs/job_config.json` and run on job clusters (autoscaling, spot-eligible) provisioned by Terraform.

### 4. Warehouse — Snowflake
- `RAW` schema: external tables / Snowpipe-ingested copies of Gold Delta tables (via ADLS Gen2 external stage).
- `STAGING` schema: views/streams that dedupe and conform Snowflake-side.
- `MARTS` schema: `FCT_TRANSACTIONS`, `DIM_CUSTOMER`, `DIM_MERCHANT`, `FRAUD_RISK_SCORES` — the layer BI tools and case-management systems query.
- `Streams & Tasks` incrementally refresh marts on new Snowpipe loads; RBAC roles (`ANALYST_RO`, `FRAUD_OPS`, `PIPELINE_LOADER`) separate load vs. read access.

### 5. Machine Learning
- Feature set: Gold-layer fraud features, joined with historical labeled fraud outcomes.
- Model: gradient-boosted classifier (XGBoost), tracked with MLflow (params, metrics, artifacts), promoted through `Staging` → `Production` in the MLflow Model Registry based on precision/recall/AUC-PR gates.
- Inference: batch scoring job writes `p_fraud` back to a Delta table and to `MARTS.FRAUD_RISK_SCORES`; a real-time path (`ml/src/serving.py`) deploys the same registered model behind a Databricks Model Serving endpoint (`fraud-risk-classifier-endpoint`) for synchronous scoring at authorization time.

### 6. Infrastructure as Code — Terraform
Modular layout (`terraform/modules/*`) for resource group, networking (VNet, subnets, private endpoints), ADLS Gen2, Databricks workspace (VNet-injected), Key Vault (secret scopes backing Databricks + Snowflake credentials), and ADF. Environments (`dev`, `prod`) are separated by tfvars files and remote state keyed by environment.

### 7. CI/CD — GitHub Actions
- `ci.yml`: lints (`ruff`/`black --check`) and runs PyTest unit tests on every push/PR.
- `terraform-plan.yml`: runs `terraform fmt -check` and `terraform plan` on PRs touching `terraform/`, posting the plan as a PR comment (`terraform apply` is gated to manual dispatch for safety).

## Design decisions

- **Medallion architecture** keeps raw data immutable and auditable — a hard requirement in regulated financial environments — while giving each downstream consumer (Snowflake, ML) a stable, quality-checked contract at the Gold layer.
- **Delta Lake in ADLS + Snowflake external tables** avoids double-loading large raw volumes into Snowflake compute while still giving analysts a governed SQL layer.
- **Databricks does the heavy transformation/ML**, Snowflake does governed serving/BI — playing each engine to its strength rather than picking one for everything.
- **Terraform modules per concern** (storage, networking, databricks, key-vault, adf) keep the stack reusable across environments and reviewable in small PRs.
