-- Snowpipe: auto-ingest chargeback/dispute settlement files as finance/chargeback-ops
-- drops them into ADLS Gen2 `raw/chargebacks/` (event-driven via the same Event Grid
-- notification integration pipe_transactions.sql uses for the Gold copy pipes).

USE SCHEMA FRAUD_PLATFORM.RAW;

CREATE PIPE IF NOT EXISTS PIPE_RAW_CHARGEBACK_OUTCOMES
  AUTO_INGEST = TRUE
  INTEGRATION = 'ADLS_EVENT_GRID_INT'
AS
COPY INTO RAW_CHARGEBACK_OUTCOMES (
  transaction_id, network, chargeback_reason_code, outcome, is_fraud_confirmed, filed_at, resolved_at
)
FROM @STG_RAW_CHARGEBACKS
FILE_FORMAT = (TYPE = CSV SKIP_HEADER = 1 FIELD_OPTIONALLY_ENCLOSED_BY = '"')
ON_ERROR = 'SKIP_FILE';

-- ALTER PIPE PIPE_RAW_CHARGEBACK_OUTCOMES REFRESH; -- manual backfill if Event Grid misses a notification
