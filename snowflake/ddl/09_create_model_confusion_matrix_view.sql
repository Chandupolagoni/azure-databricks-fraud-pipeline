-- MARTS.VW_DAILY_MODEL_CONFUSION_MATRIX / VW_MODEL_PRECISION_RECALL_TREND_30D
--
-- ml/src/monitor_drift.py already computes a live AUC-PR off VW_RECONCILED_SCORED_TRANSACTIONS
-- (05_create_fraud_outcomes.sql) and alerts when it drifts from the training-time promotion
-- gate, but that number only surfaces on job failure and isn't broken out by day or by the
-- underlying confusion-matrix counts. Fraud-ops and the model-owning team often want to eyeball
-- "is precision or recall the thing moving, and since when" without pulling the drift job's logs
-- or re-running a notebook, so this sits alongside the drift monitor as a human-browsable,
-- always-current warehouse view over the same reconciled population.
--
-- Grouped by reconciled_at date and model_version rather than scored_at: a transaction's
-- fraud/not-fraud label isn't known until the chargeback window closes (see
-- 07_create_chargeback_outcomes_feed.sql), so "today's" confusion-matrix row reflects
-- transactions reconciled today, which were typically scored T-30 to T-90 days earlier --
-- the same lag the drift monitor already accounts for via MIN_RECONCILED_SAMPLES.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE OR REPLACE VIEW VW_DAILY_MODEL_CONFUSION_MATRIX AS
SELECT
  DATE_TRUNC('day', reconciled_at)                                       AS reconciled_date,
  model_version,
  COUNT(*)                                                                AS reconciled_txn_count,
  SUM(IFF(is_flagged AND is_fraud, 1, 0))                                AS true_positives,
  SUM(IFF(is_flagged AND NOT is_fraud, 1, 0))                            AS false_positives,
  SUM(IFF(NOT is_flagged AND is_fraud, 1, 0))                            AS false_negatives,
  SUM(IFF(NOT is_flagged AND NOT is_fraud, 1, 0))                        AS true_negatives,
  ROUND(SUM(IFF(is_flagged AND is_fraud, 1, 0))
    / NULLIF(SUM(IFF(is_flagged, 1, 0)), 0), 4)                          AS precision_score,
  ROUND(SUM(IFF(is_flagged AND is_fraud, 1, 0))
    / NULLIF(SUM(IFF(is_fraud, 1, 0)), 0), 4)                            AS recall_score,
  ROUND(SUM(IFF(is_flagged AND NOT is_fraud, 1, 0))
    / NULLIF(SUM(IFF(NOT is_fraud, 1, 0)), 0), 4)                        AS false_positive_rate
FROM VW_RECONCILED_SCORED_TRANSACTIONS
GROUP BY DATE_TRUNC('day', reconciled_at), model_version;

-- Trailing-30-day trend, most recent first, for the dashboard/runbook query fraud-ops and the
-- model owner actually run day to day -- same "pre-filtered, pre-sorted sibling view" pattern
-- as VW_MERCHANT_RISK_TRIAGE_QUEUE / VW_ACCOUNT_VELOCITY_TRIAGE_QUEUE.
CREATE OR REPLACE VIEW VW_MODEL_PRECISION_RECALL_TREND_30D AS
SELECT *
FROM VW_DAILY_MODEL_CONFUSION_MATRIX
WHERE reconciled_date >= DATEADD(day, -30, CURRENT_DATE())
ORDER BY reconciled_date DESC, model_version;
