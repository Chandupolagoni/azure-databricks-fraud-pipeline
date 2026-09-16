# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Run All
# MAGIC Orchestrates the medallion notebooks in order. This is the notebook ADF's
# MAGIC `RunDatabricksMedallionJob` activity invokes (see `adf/pipelines/pl_orchestrate_full_pipeline.json`).
# MAGIC In production this logic is expressed as a multi-task Databricks Job
# MAGIC (`databricks/jobs/job_config.json`) rather than notebook-to-notebook `%run`, but is
# MAGIC included here for local/manual runs.

# COMMAND ----------

dbutils.widgets.text("run_date", "")
dbutils.widgets.text("storage_account", "stfraudplatformdevabcde")

run_date = dbutils.widgets.get("run_date")
storage_account = dbutils.widgets.get("storage_account")

# COMMAND ----------

for nb in [
    "01_bronze_ingestion",
    "02_silver_transformations",
    "03_gold_aggregations",
    "04_feature_engineering",
]:
    print(f"Running {nb} ...")
    dbutils.notebook.run(
        nb,
        timeout_seconds=3600,
        arguments={"storage_account": storage_account, "run_date": run_date},
    )

print("Medallion pipeline complete.")
