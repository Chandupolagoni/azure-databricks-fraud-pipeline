-- Streams & Tasks: incrementally refresh MARTS whenever new rows land via Snowpipe.
-- ADF's `TriggerSnowflakeMartRefresh` activity calls `EXECUTE TASK` on the root task,
-- but the tree is also wired to run on its own schedule as a safety net.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE TASK IF NOT EXISTS TASK_REFRESH_MARTS
  WAREHOUSE = WH_LOADER
  SCHEDULE = 'USING CRON 15 5 * * * UTC'
  WHEN SYSTEM$STREAM_HAS_DATA('FRAUD_PLATFORM.STAGING.STRM_RAW_TRANSACTIONS')
AS
  CALL FRAUD_PLATFORM.MARTS.SP_LOAD_FRAUD_MARTS();

CREATE TASK IF NOT EXISTS TASK_REFRESH_FRAUD_SCORES
  WAREHOUSE = WH_LOADER
  AFTER TASK_REFRESH_MARTS
  WHEN SYSTEM$STREAM_HAS_DATA('FRAUD_PLATFORM.STAGING.STRM_RAW_FRAUD_FEATURES')
AS
  MERGE INTO FRAUD_RISK_SCORES tgt
  USING (
    SELECT
      transaction_id,
      'batch-scored-externally' AS model_version,
      NULL AS p_fraud,
      FALSE AS is_flagged
    FROM FRAUD_PLATFORM.STAGING.STRM_RAW_FRAUD_FEATURES
  ) src
  ON tgt.transaction_id = src.transaction_id
  WHEN NOT MATCHED THEN
    INSERT (transaction_id, model_version, p_fraud, is_flagged)
    VALUES (src.transaction_id, src.model_version, src.p_fraud, src.is_flagged);

ALTER TASK TASK_REFRESH_FRAUD_SCORES RESUME;
ALTER TASK TASK_REFRESH_MARTS RESUME;
