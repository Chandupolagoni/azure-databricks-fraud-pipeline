-- MARTS.VW_ACCOUNT_VELOCITY_WATCHLIST: per-account rollup for fraud-ops triage.
--
-- VW_MERCHANT_RISK_SUMMARY (06_create_merchant_risk_view.sql) gives fraud-ops a merchant-side
-- view; there was no equivalent account-side view, even though DIM_CUSTOMER.risk_segment is
-- itself a static, offline-recomputed label (like DIM_MERCHANT.merchant_risk_score) that can
-- lag a customer who started transacting unusually this week. This view sits alongside it:
-- a rolling, transaction-level flagged rate and velocity over the trailing 7 days, joined back
-- to the static segment, so fraud-ops can see both the long-run prior and the live signal
-- without cross-referencing DIM_CUSTOMER by hand. A shorter 7-day window is used here (vs. the
-- merchant view's 30-day window) since account-level fraud bursts tend to play out over days,
-- not weeks, and a month-long window would smooth a short, sharp spike away.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE OR REPLACE VIEW VW_ACCOUNT_VELOCITY_WATCHLIST AS
WITH trailing_7d AS (
  SELECT
    f.account_id,
    COUNT(*)                                            AS txn_count_7d,
    COUNT(DISTINCT f.merchant_id)                       AS distinct_merchants_7d,
    SUM(IFF(r.is_flagged, 1, 0))                        AS flagged_count_7d,
    SUM(f.amount)                                        AS txn_volume_7d,
    SUM(IFF(r.is_flagged, f.amount, 0))                 AS flagged_volume_7d
  FROM FCT_TRANSACTIONS f
  LEFT JOIN FRAUD_RISK_SCORES r ON f.transaction_id = r.transaction_id
  WHERE f.transaction_date >= DATEADD(day, -7, CURRENT_DATE())
  GROUP BY f.account_id
)
SELECT
  c.account_id,
  c.risk_segment                                                  AS historical_risk_segment,
  COALESCE(t.txn_count_7d, 0)                                     AS txn_count_7d,
  COALESCE(t.distinct_merchants_7d, 0)                            AS distinct_merchants_7d,
  COALESCE(t.flagged_count_7d, 0)                                 AS flagged_count_7d,
  ROUND(COALESCE(t.flagged_count_7d, 0)
    / NULLIF(t.txn_count_7d, 0), 4)                               AS flagged_rate_7d,
  COALESCE(t.txn_volume_7d, 0)                                    AS txn_volume_7d,
  COALESCE(t.flagged_volume_7d, 0)                                AS flagged_volume_7d,
  CASE
    WHEN t.txn_count_7d < 5 THEN 'INSUFFICIENT_VOLUME'
    WHEN COALESCE(t.flagged_count_7d, 0) / NULLIF(t.txn_count_7d, 0) >= 0.25 THEN 'HIGH'
    WHEN COALESCE(t.flagged_count_7d, 0) / NULLIF(t.txn_count_7d, 0) >= 0.10 THEN 'ELEVATED'
    ELSE 'NORMAL'
  END                                                              AS velocity_tier
FROM DIM_CUSTOMER c
LEFT JOIN trailing_7d t ON c.account_id = t.account_id;

-- Fraud-ops triage queue: accounts flagged HIGH or ELEVATED, worst first, plus a secondary
-- sort on distinct merchant spread so a single account hitting many different merchants in
-- the window (a common card-testing / account-takeover pattern) surfaces ahead of one with
-- the same flagged rate concentrated at a single merchant.
CREATE OR REPLACE VIEW VW_ACCOUNT_VELOCITY_TRIAGE_QUEUE AS
SELECT *
FROM VW_ACCOUNT_VELOCITY_WATCHLIST
WHERE velocity_tier IN ('HIGH', 'ELEVATED')
ORDER BY flagged_rate_7d DESC NULLS LAST, distinct_merchants_7d DESC;
