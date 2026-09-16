# Azure Databricks + Snowflake Fraud & Risk Analytics Platform

[![Terraform Plan](https://github.com/Chandupolagoni/azure-databricks-fraud-pipeline/actions/workflows/terraform-plan.yml/badge.svg)](../../actions/workflows/terraform-plan.yml)
[![CI](https://github.com/Chandupolagoni/azure-databricks-fraud-pipeline/actions/workflows/ci.yml/badge.svg)](../../actions/workflows/ci.yml)

End-to-end, production-style data engineering platform for a financial services company, built to demonstrate the full lifecycle: **infrastructure as code → ingestion → transformation → warehousing → ML → orchestration → CI/CD**.

> This is a portfolio / reference implementation. It uses synthetic transaction data and is designed to be read, run locally against sample data, and deployed to a real Azure subscription by supplying your own `terraform.tfvars` and secrets. No real financial data or credentials are included in this repository.

## Why this project exists

Financial institutions need a fraud & risk analytics pipeline that is auditable, reproducible, and fast to extend. This repo shows how I'd build that: Terraform-provisioned Azure infrastructure, Azure Data Factory for orchestration, Databricks/PySpark for large-scale transformation and feature engineering, Snowflake as the governed analytics warehouse, and MLflow-tracked fraud-detection models served back into the pipeline.

## Architecture

See [`architecture/architecture.md`](architecture/architecture.md) for the full write-up, data flow, and design decisions.

```
Source Systems (core banking, cards, digital) 
        │
        ▼
Azure Data Factory  ──(orchestrates)──►  Databricks (PySpark)
        │  Bronze (raw, ADLS Gen2)             │  Silver (cleansed) → Gold (curated)
        │                                       │  Feature engineering → MLflow models
        ▼                                       ▼
   ADLS Gen2 (raw + curated zones)     Snowflake (EDW: RAW → STAGING → MARTS)
                                                 │
                                                 ▼
                                     BI / Fraud Scoring / Case Management
```

## Repository layout

| Path | Contents |
|---|---|
| `terraform/` | Modular IaC for resource group, ADLS Gen2, Databricks workspace, VNet/private endpoints, Key Vault, and ADF |
| `adf/` | Azure Data Factory pipelines, datasets, linked services, and triggers (ARM/JSON export format) |
| `databricks/` | PySpark notebooks and reusable src modules for Bronze → Silver → Gold and feature engineering |
| `snowflake/` | DDL, Snowpipe, streams/tasks, and stored procedures for the RAW → STAGING → MARTS warehouse |
| `ml/` | Fraud model training, evaluation, inference, and MLflow project for the risk-scoring model |
| `tests/` | PyTest unit tests for transformation and feature logic |
| `.github/workflows/` | CI (lint + test) and Terraform plan-on-PR pipelines |
| `docs/` | Data dictionary, operational runbook, and changelog |

## Tech stack

- **IaC:** Terraform (azurerm + databricks providers)
- **Storage:** Azure Data Lake Storage Gen2 (hierarchical namespace, medallion zones)
- **Orchestration:** Azure Data Factory
- **Compute / Transformation:** Azure Databricks, PySpark, Delta Lake
- **Warehouse:** Snowflake (Snowpipe, Streams & Tasks, RBAC)
- **ML:** scikit-learn / XGBoost, MLflow tracking & model registry
- **Languages:** Python, PySpark, SQL (Snowflake + Spark SQL), HCL
- **CI/CD:** GitHub Actions

## Getting started (local / sample data)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v
```

## Deploying the infrastructure

```bash
cd terraform
terraform init
terraform plan -var-file=environments/dev.tfvars
terraform apply -var-file=environments/dev.tfvars
```

See [`docs/runbook.md`](docs/runbook.md) for the full deployment and operations runbook, including Snowflake and Databricks post-provisioning steps.

## Practicing/demoing without a full Azure deployment

`databricks/notebooks/free_edition/` has drop-in equivalents of the medallion notebooks that run on [Databricks Free Edition](https://www.databricks.com/learn/free-edition) against Unity Catalog volumes instead of ADLS Gen2 — useful for validating the PySpark transformation logic and grabbing screenshots without provisioning any Azure infrastructure. See [`docs/free_edition_practice.md`](docs/free_edition_practice.md).

## Data flow (medallion architecture)

1. **Bronze** – raw transaction, card, and customer events land in ADLS Gen2 `raw/` via ADF copy activities, schema-on-read, append-only Delta tables.
2. **Silver** – Databricks notebooks cleanse, deduplicate, conform types, and apply data-quality rules (`databricks/notebooks/02_silver_transformations.py`).
3. **Gold** – business-level aggregates and fraud-relevant features (velocity, geo-mismatch, device fingerprint reuse) are computed (`databricks/notebooks/03_gold_aggregations.py`, `04_feature_engineering.py`).
4. **Warehouse** – Gold Delta tables are loaded into Snowflake via Snowpipe/external tables; `snowflake/` builds the RAW → STAGING → MARTS layers analysts and BI tools query.
5. **ML** – `ml/src/train.py` trains a gradient-boosted fraud classifier on the Gold feature set, logs runs to MLflow, and registers the best model; `ml/src/inference.py` shows batch scoring back into Delta/Snowflake.

## Project status

This project is under active, incremental development — new modules, tests, and docs are added on an ongoing basis (see [`docs/CHANGELOG.md`](docs/CHANGELOG.md)).

## License

MIT — see [`LICENSE`](LICENSE).
