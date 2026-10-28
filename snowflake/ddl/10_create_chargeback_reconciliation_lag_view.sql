-- MARTS.VW_CHARGEBACK_RECONCILIATION_AGING: open (unresolved) chargeback/dispute backlog.
--
-- SP_RECONCILE_FRAUD_OUTCOMES (snowflake/procedures/sp_reconcile_fraud_outcomes.sql) only
-- ever surfaces a dispute once it's resolved -- CONFIRMED_FRAUD_OUTCOMES gets no row, and
-- there's no way to tell fraud-ops/finance how a dispute is doing while it's still open.
-- The feed's own comment (snowflake/ddl/07_create_chargeback_outcomes_feed.sql) notes
-- issuers resolve disputes on a T+30 to T+90 day timeline; this view ages the backlog
-- against that window so a dispute sitting open well past it surfaces before it quietly
-- falls out of anyone's attention. It also flags the one case
-- SP_RECONCILE_FRAUD_OUTCOMES's own merge logic can never resolve by itself: a chargeback
-- filed against a transaction_id that hasn't landed in FCT_TRANSACTIONS yet, which the
-- procedure's join silently skips every run until ingestion catches up -- without this
-- view, that case was indistinguishable from a dispute simply still awaiting the issuer.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE OR REPLACE VIEW VW_CHARGEBACK_RECONCILIATION_AGING AS
WITH open_disputes AS (
  -- One row per transaction_id: a dispute can be re-filed/corrected while still open,
  -- so the most recently filed record wins -- mirrors SP_RECONCILE_FRAUD_OUTCOMES's own
  -- dedupe-by-transaction_id pattern (there, ordered by resolved_at instead of filed_at).
  SELECT
    c.transaction_id,
    c.network,
    c.chargeback_reason_code,
    c.filed_at,
    ROW_NUMBER() OVER (
      PARTITION BY c.transaction_id ORDER BY c.filed_at DESC
    ) AS rn
  FROM FRAUD_PLATFORM.RAW.RAW_CHARGEBACK_OUTCOMES c
  WHERE c.resolved_at IS NULL
)
SELECT
  d.transaction_id,
  d.network,
  d.chargeback_reason_code,
  d.filed_at,
  DATEDIFF(day, d.filed_at, CURRENT_TIMESTAMP())                 AS days_open,
  IFF(f.transaction_id IS NULL, TRUE, FALSE)                     AS awaiting_transaction_ingest,
  CASE
    WHEN DATEDIFF(day, d.filed_at, CURRENT_TIMESTAMP()) >= 90 THEN 'SLA_BREACH'
    WHEN DATEDIFF(day, d.filed_at, CURRENT_TIMESTAMP()) >= 30 THEN 'WITHIN_EXPECTED_RANGE'
    ELSE 'RECENT'
  END                                                              AS aging_tier
FROM open_disputes d
LEFT JOIN FCT_TRANSACTIONS f ON f.transaction_id = d.transaction_id
WHERE d.rn = 1;

-- Finance/fraud-ops triage queue: disputes past the T+90 day SLA window, or stuck
-- waiting on transaction ingestion (which SP_RECONCILE_FRAUD_OUTCOMES can't fix on its
-- own -- that needs an ingestion-side look, not a reconciliation re-run), oldest first.
CREATE OR REPLACE VIEW VW_CHARGEBACK_RECONCILIATION_SLA_BREACH_QUEUE AS
SELECT *
FROM VW_CHARGEBACK_RECONCILIATION_AGING
WHERE aging_tier = 'SLA_BREACH' OR awaiting_transaction_ingest
ORDER BY days_open DESC;
