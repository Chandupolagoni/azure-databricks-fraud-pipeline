-- MARTS.CONFIRMED_FRAUD_OUTCOMES: ground-truth fraud outcomes reconciled after the
-- card-network chargeback/dispute window closes (typically T+30 to T+90 days).
-- Feeds the live model-quality drift monitor (ml/src/monitor_drift.py), which joins
-- this back against FRAUD_RISK_SCORES to compute a live AUC-PR and compare it to the
-- same promotion gate used at training time (train.py::PROMOTION_AUC_PR_THRESHOLD).

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE TABLE IF NOT EXISTS CONFIRMED_FRAUD_OUTCOMES (
  transaction_id    STRING PRIMARY KEY REFERENCES FCT_TRANSACTIONS(transaction_id),
  is_fraud          BOOLEAN NOT NULL,
  outcome_source    STRING,   -- e.g. 'chargeback', 'issuer_confirmed', 'customer_dispute'
  reconciled_at     TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
  _loaded_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

-- One row per transaction whose outcome has been reconciled and that already has a
-- model score on file — the exact population the drift monitor scores against.
CREATE OR REPLACE VIEW VW_RECONCILED_SCORED_TRANSACTIONS AS
SELECT
  r.transaction_id,
  r.model_version,
  r.p_fraud,
  r.is_flagged,
  r.scored_at,
  o.is_fraud,
  o.outcome_source,
  o.reconciled_at
FROM FRAUD_RISK_SCORES r
INNER JOIN CONFIRMED_FRAUD_OUTCOMES o ON r.transaction_id = o.transaction_id;
