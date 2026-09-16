# Running the pipeline in Databricks Free Edition

Free Edition doesn't support custom external storage (no ADLS/S3 mounting) or
account-level provisioning, so `terraform/` and the `abfss://`-based notebooks in
`databricks/notebooks/` don't apply directly. `databricks/notebooks/free_edition/`
has drop-in equivalents that read/write **Unity Catalog managed tables and volumes**
instead — same transformation logic (they import the exact same
`databricks/src/transformations/*` modules), just a different storage layer. This is
for practicing/demoing the PySpark logic and getting screenshots for a portfolio
walkthrough — it does not exercise the Terraform/ADF/Snowflake parts of the project.

## 1. Generate synthetic sample data (locally, on your machine)

```bash
pip install -r requirements.txt   # only need stdlib actually, but keeps env consistent
python scripts/generate_synthetic_data.py --out-dir ./sample_data --rows 2000
```

This writes:
- `sample_data/card-network/transactions.csv` — synthetic transactions (same columns as `TRANSACTION_SCHEMA_COLUMNS` in `cleansing.py`), including a few injected cross-country pairs so the impossible-travel feature has something to catch
- `sample_data/merchant_risk_lookup.csv` — a risk score per merchant category

## 2. Set up the workspace

1. Sign in to [Databricks Free Edition](https://www.databricks.com/learn/free-edition).
2. Attach this repo via **Repos** (`Workspace > Repos > Add Repo`, paste the GitHub URL) so the notebooks can `sys.path.append` the shared `databricks/src` modules — or just upload the `databricks/notebooks/free_edition/*.py` files individually via **Workspace > Import** if you'd rather not clone the whole repo in.
3. Open `free_edition/00_setup_catalog.py`, run it (defaults: catalog `main`, schema `fraud_platform`). It creates the schema and two Unity Catalog volumes (`raw`, `curated`).

## 3. Upload the sample data into the `raw` volume

In **Catalog Explorer**, navigate to `main.fraud_platform.raw`, and upload:
- `sample_data/card-network/transactions.csv` → into a `card-network/` folder inside the volume
- `sample_data/merchant_risk_lookup.csv` → into a `merchant_risk_lookup/` folder inside the volume

(Catalog Explorer's "Upload to volume" button handles the folder creation; or use `%sh cp` from a notebook cell pointed at `/Volumes/main/fraud_platform/raw/...` if you uploaded the CSVs to the workspace's Files first.)

## 4. Run the notebooks in order

1. `free_edition/01_bronze_ingestion.py` — reads the CSV, writes `main.fraud_platform.bronze_card_network`
2. `free_edition/02_silver_transformations.py` — cleansing/dedup/tokenization/DQ, writes `silver_transactions` (+ `silver_transactions_quarantine`)
3. `free_edition/03_gold_aggregations.py` — writes `gold_daily_customer_spend`, `gold_merchant_category_exposure`
4. `free_edition/04_feature_engineering.py` — writes `gold_fraud_features` (the velocity/geo/device/merchant-risk features)

Each notebook has `display()` calls at the end — good spots to screenshot for a walkthrough.

## 5. Suggested demo moments

- **Bronze**: show `_ingested_at`/`_source_file` audit columns proving lineage.
- **Silver**: query `silver_transactions_quarantine` and show a rejected row (negative amount, missing account) — demonstrates the DQ-flag-not-drop design from `architecture.md`.
- **Gold features**: `SELECT * FROM main.fraud_platform.gold_fraud_features WHERE is_impossible_travel = true` — shows the geo-velocity fraud signal firing on the synthetic cross-country transactions.
- Run `ml/src/train.py --synthetic` locally (outside Databricks) afterward to show the same feature columns feeding a trained MLflow model end-to-end.

## Cleanup

`DROP SCHEMA main.fraud_platform CASCADE` removes everything created here — Free Edition has a single shared workspace/metastore, so it's worth tidying up between practice sessions.
