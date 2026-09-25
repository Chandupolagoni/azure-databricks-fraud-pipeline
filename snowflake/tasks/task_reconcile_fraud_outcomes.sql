-- Streams & Tasks: reconcile chargeback/dispute outcomes into CONFIRMED_FRAUD_OUTCOMES
-- whenever new resolved rows land via Snowpipe (PIPE_RAW_CHARGEBACK_OUTCOMES), with a
-- daily schedule as a safety net -- mirrors TASK_REFRESH_MARTS's pattern in
-- task_refresh_marts.sql. Runs independently of the transaction-loading task tree since
-- chargeback resolution lags transaction ingestion by weeks, not minutes.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE TASK IF NOT EXISTS TASK_RECONCILE_FRAUD_OUTCOMES
  WAREHOUSE = WH_LOADER
  SCHEDULE = 'USING CRON 30 6 * * * UTC'
  WHEN SYSTEM$STREAM_HAS_DATA('FRAUD_PLATFORM.STAGING.STRM_RAW_CHARGEBACK_OUTCOMES')
AS
  CALL FRAUD_PLATFORM.MARTS.SP_RECONCILE_FRAUD_OUTCOMES();

ALTER TASK TASK_RECONCILE_FRAUD_OUTCOMES RESUME;
