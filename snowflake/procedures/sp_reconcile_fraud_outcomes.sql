-- Stored procedure: merges resolved chargeback/dispute outcomes from the staging stream
-- into MARTS.CONFIRMED_FRAUD_OUTCOMES, the ground-truth table ml/src/monitor_drift.py's
-- live drift check reads from. Until this ran, the table DDL existed
-- (snowflake/ddl/05_create_fraud_outcomes.sql) but nothing populated it.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE OR REPLACE PROCEDURE SP_RECONCILE_FRAUD_OUTCOMES()
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
  MERGE INTO CONFIRMED_FRAUD_OUTCOMES tgt
  USING (
    -- One row per transaction: last-resolved outcome wins if a network sends a
    -- correction after the initial resolution. Only transactions with a
    -- FCT_TRANSACTIONS row can be inserted (FK constraint on CONFIRMED_FRAUD_OUTCOMES) --
    -- a chargeback filed against a transaction the platform hasn't ingested yet is
    -- skipped here and picked up on a later run once FCT_TRANSACTIONS catches up.
    SELECT transaction_id, is_fraud_confirmed, network, resolved_at
    FROM (
      SELECT
        c.transaction_id,
        c.is_fraud_confirmed,
        c.network,
        c.resolved_at,
        ROW_NUMBER() OVER (
          PARTITION BY c.transaction_id ORDER BY c.resolved_at DESC
        ) AS rn
      FROM FRAUD_PLATFORM.STAGING.STRM_RAW_CHARGEBACK_OUTCOMES c
      INNER JOIN FCT_TRANSACTIONS f ON f.transaction_id = c.transaction_id
      WHERE c.resolved_at IS NOT NULL
    )
    WHERE rn = 1
  ) src
  ON tgt.transaction_id = src.transaction_id
  WHEN MATCHED THEN
    UPDATE SET
      is_fraud       = src.is_fraud_confirmed,
      outcome_source = 'chargeback:' || src.network,
      reconciled_at  = src.resolved_at
  WHEN NOT MATCHED THEN
    INSERT (transaction_id, is_fraud, outcome_source, reconciled_at)
    VALUES (src.transaction_id, src.is_fraud_confirmed, 'chargeback:' || src.network, src.resolved_at);

  RETURN 'SP_RECONCILE_FRAUD_OUTCOMES complete: ' || CURRENT_TIMESTAMP()::STRING;
END;
$$;
