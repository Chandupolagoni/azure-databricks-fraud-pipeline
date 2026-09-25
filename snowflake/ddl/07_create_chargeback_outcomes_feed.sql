-- RAW/STAGING ingestion for card-network chargeback/dispute outcomes.
-- Issuers resolve disputes on their own timeline (typically T+30 to T+90 days), so this
-- lands as a separate reconciliation feed rather than riding along with the Gold
-- Delta/Parquet copy pipes in pipe_transactions.sql. The finance/chargeback-ops team drops
-- one file per network settlement batch into ADLS Gen2 `raw/chargebacks/`; Snowpipe below
-- auto-ingests it the same way PIPE_RAW_TRANSACTIONS does for the Gold copies.
--
-- SP_RECONCILE_FRAUD_OUTCOMES (snowflake/procedures/sp_reconcile_fraud_outcomes.sql) and
-- TASK_RECONCILE_FRAUD_OUTCOMES (snowflake/tasks/task_reconcile_fraud_outcomes.sql) turn the
-- stream below into rows in MARTS.CONFIRMED_FRAUD_OUTCOMES, which
-- ml/src/monitor_drift.py's live drift check reads from.

USE SCHEMA FRAUD_PLATFORM.RAW;

CREATE STAGE IF NOT EXISTS STG_RAW_CHARGEBACKS
  STORAGE_INTEGRATION = ADLS_FRAUD_PLATFORM_INT
  URL = 'azure://stfraudplatformprod.blob.core.windows.net/raw/chargebacks/'
  FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"');

CREATE TABLE IF NOT EXISTS RAW_CHARGEBACK_OUTCOMES (
  transaction_id        STRING,
  network                STRING,   -- 'VISA' | 'MASTERCARD' | 'AMEX' | 'DISCOVER'
  chargeback_reason_code STRING,
  outcome                STRING,   -- 'MERCHANT_WON' | 'MERCHANT_LOST' | 'WITHDRAWN'
  is_fraud_confirmed     BOOLEAN,  -- issuer-confirmed fraud, distinct from a non-fraud dispute (e.g. billing error)
  filed_at               TIMESTAMP_NTZ,
  resolved_at            TIMESTAMP_NTZ,
  _loaded_at             TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- Snowpipe ingestion for this stage/table lives in snowflake/snowpipe/pipe_chargeback_outcomes.sql,
-- matching pipe_transactions.sql's split from its own RAW table DDL.

USE SCHEMA FRAUD_PLATFORM.STAGING;

-- Only resolved disputes are reconciliation-ready; SP_RECONCILE_FRAUD_OUTCOMES filters on
-- resolved_at IS NOT NULL again defensively, but excluding open disputes here keeps the
-- stream from being re-consumed by the task before there's an outcome to reconcile.
CREATE STREAM IF NOT EXISTS STRM_RAW_CHARGEBACK_OUTCOMES
  ON TABLE FRAUD_PLATFORM.RAW.RAW_CHARGEBACK_OUTCOMES
  APPEND_ONLY = TRUE;
