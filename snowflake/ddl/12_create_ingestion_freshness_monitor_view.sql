-- MARTS.VW_INGESTION_FRESHNESS_MONITOR, MARTS.VW_INGESTION_FRESHNESS_ALERT_QUEUE
--
-- VW_TASK_FAILURE_MONITOR (snowflake/ddl/11_create_task_failure_monitor_view.sql) closed the
-- visibility gap for the warehouse-side task graph, and adf_pipeline_failure
-- (terraform/modules/monitoring) closed it for the orchestration side -- but the Snowpipe
-- auto-ingest step feeding RAW_TRANSACTIONS/RAW_FRAUD_FEATURES from ADLS Gen2
-- (snowflake/snowpipe/pipe_transactions.sql) sits between those two and has no failure
-- trail of its own: a pipe is not a task, so a suspended pipe, an expired storage
-- integration credential, or a missed Event Grid notification never produces a row in
-- ACCOUNT_USAGE.TASK_HISTORY. Today that only shows up indirectly once a downstream
-- task/view goes thin -- the exact "notice the symptom, not the cause" gap the task
-- failure monitor and chargeback aging view already closed one layer down the stack.
--
-- This checks ingestion recency directly against each RAW table's own `_loaded_at`
-- watermark instead: RAW_TRANSACTIONS is event-driven (AUTO_INGEST = TRUE off Event Grid)
-- so a multi-hour gap is already abnormal; RAW_FRAUD_FEATURES only lands once per Gold
-- batch run (04_feature_engineering.py, daily), so its expected gap is sized to that
-- cadence plus a buffer rather than reusing the transactions threshold.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE OR REPLACE VIEW VW_INGESTION_FRESHNESS_MONITOR AS
WITH expected_cadence AS (
  -- RAW_TRANSACTIONS: continuous event-driven Snowpipe, so even a short stall is unusual.
  SELECT 'RAW_TRANSACTIONS' AS table_name, 180 AS expected_max_gap_minutes
  UNION ALL
  -- RAW_FRAUD_FEATURES: one landing per daily Gold batch run plus buffer for a late run.
  SELECT 'RAW_FRAUD_FEATURES' AS table_name, 1620 AS expected_max_gap_minutes
),
last_loaded AS (
  SELECT 'RAW_TRANSACTIONS' AS table_name, MAX(_loaded_at) AS last_loaded_at
  FROM FRAUD_PLATFORM.RAW.RAW_TRANSACTIONS
  UNION ALL
  SELECT 'RAW_FRAUD_FEATURES' AS table_name, MAX(_loaded_at) AS last_loaded_at
  FROM FRAUD_PLATFORM.RAW.RAW_FRAUD_FEATURES
)
SELECT
  c.table_name,
  l.last_loaded_at,
  DATEDIFF('minute', l.last_loaded_at, CURRENT_TIMESTAMP())  AS minutes_since_last_load,
  c.expected_max_gap_minutes,
  (l.last_loaded_at IS NULL
    OR DATEDIFF('minute', l.last_loaded_at, CURRENT_TIMESTAMP()) > c.expected_max_gap_minutes
  )                                                           AS is_stale
FROM expected_cadence c
JOIN last_loaded l USING (table_name);

-- Triage queue: just the tables currently breaching their expected cadence, worst gap
-- first -- mirrors the _SUMMARY/_TRIAGE_QUEUE split used by the merchant risk and
-- chargeback aging views.
CREATE OR REPLACE VIEW VW_INGESTION_FRESHNESS_ALERT_QUEUE AS
SELECT *
FROM VW_INGESTION_FRESHNESS_MONITOR
WHERE is_stale
ORDER BY minutes_since_last_load DESC NULLS FIRST;
