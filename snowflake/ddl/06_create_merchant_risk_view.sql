-- MARTS.VW_MERCHANT_RISK_SUMMARY: per-merchant rollup for fraud-ops triage.
--
-- DIM_MERCHANT.merchant_risk_score is the historical, chargeback-rate-derived category
-- score computed offline (see docs/data_dictionary.md). It does not move until the next
-- offline recompute, so it can't reflect a merchant that started trending hot this week.
-- This view sits alongside it: a rolling, transaction-level flagged rate over the trailing
-- 30 days, joined back to the static score, so fraud-ops can see both the long-run prior
-- and the live signal in one place instead of cross-referencing DIM_MERCHANT by hand.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE OR REPLACE VIEW VW_MERCHANT_RISK_SUMMARY AS
WITH trailing_30d AS (
  SELECT
    f.merchant_id,
    COUNT(*)                                          AS txn_count_30d,
    SUM(IFF(r.is_flagged, 1, 0))                       AS flagged_count_30d,
    SUM(f.amount)                                       AS txn_volume_30d,
    SUM(IFF(r.is_flagged, f.amount, 0))                 AS flagged_volume_30d
  FROM FCT_TRANSACTIONS f
  LEFT JOIN FRAUD_RISK_SCORES r ON f.transaction_id = r.transaction_id
  WHERE f.transaction_date >= DATEADD(day, -30, CURRENT_DATE())
  GROUP BY f.merchant_id
)
SELECT
  m.merchant_id,
  m.merchant_category,
  m.merchant_risk_score                                          AS historical_risk_score,
  COALESCE(t.txn_count_30d, 0)                                    AS txn_count_30d,
  COALESCE(t.flagged_count_30d, 0)                                AS flagged_count_30d,
  ROUND(COALESCE(t.flagged_count_30d, 0)
    / NULLIF(t.txn_count_30d, 0), 4)                              AS flagged_rate_30d,
  COALESCE(t.txn_volume_30d, 0)                                   AS txn_volume_30d,
  COALESCE(t.flagged_volume_30d, 0)                                AS flagged_volume_30d,
  -- Simple divergence signal: how far the trailing live flagged rate has drifted from
  -- the static historical score, in absolute points. Large positive values are merchants
  -- worth a manual look before the next offline score recompute catches up to them.
  ROUND(
    COALESCE(t.flagged_count_30d, 0) / NULLIF(t.txn_count_30d, 0) - m.merchant_risk_score,
    4
  )                                                                AS risk_score_divergence,
  CASE
    WHEN t.txn_count_30d < 20 THEN 'INSUFFICIENT_VOLUME'
    WHEN COALESCE(t.flagged_count_30d, 0) / NULLIF(t.txn_count_30d, 0) >= 0.10 THEN 'HIGH'
    WHEN COALESCE(t.flagged_count_30d, 0) / NULLIF(t.txn_count_30d, 0) >= 0.03 THEN 'ELEVATED'
    ELSE 'NORMAL'
  END                                                              AS risk_tier
FROM DIM_MERCHANT m
LEFT JOIN trailing_30d t ON m.merchant_id = t.merchant_id;

-- Fraud-ops triage queue: merchants flagged HIGH or ELEVATED, worst first. Backs the
-- "merchants to review today" panel referenced in docs/runbook.md.
CREATE OR REPLACE VIEW VW_MERCHANT_RISK_TRIAGE_QUEUE AS
SELECT *
FROM VW_MERCHANT_RISK_SUMMARY
WHERE risk_tier IN ('HIGH', 'ELEVATED')
ORDER BY flagged_rate_30d DESC NULLS LAST;
