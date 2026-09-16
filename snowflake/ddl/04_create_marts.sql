-- MARTS schema: the star schema BI tools, fraud-ops case management, and analysts query.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE TABLE IF NOT EXISTS DIM_CUSTOMER (
  account_id       STRING PRIMARY KEY,
  onboarding_date  DATE,
  risk_segment     STRING,
  _updated_at      TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS DIM_MERCHANT (
  merchant_id        STRING PRIMARY KEY,
  merchant_category   STRING,
  merchant_risk_score FLOAT,
  _updated_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS FCT_TRANSACTIONS (
  transaction_id     STRING PRIMARY KEY,
  account_id         STRING REFERENCES DIM_CUSTOMER(account_id),
  merchant_id        STRING REFERENCES DIM_MERCHANT(merchant_id),
  amount             NUMBER(18,2),
  currency           STRING,
  transaction_ts     TIMESTAMP_NTZ,
  transaction_date   DATE,
  channel            STRING,
  country_code       STRING,
  _loaded_at         TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS FRAUD_RISK_SCORES (
  transaction_id   STRING PRIMARY KEY REFERENCES FCT_TRANSACTIONS(transaction_id),
  model_version    STRING,
  p_fraud          FLOAT,
  is_flagged       BOOLEAN,
  scored_at        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE OR REPLACE VIEW VW_DAILY_FRAUD_SUMMARY AS
SELECT
  f.transaction_date,
  COUNT(*)                                            AS total_transactions,
  SUM(IFF(r.is_flagged, 1, 0))                        AS flagged_transactions,
  ROUND(SUM(IFF(r.is_flagged, 1, 0)) / COUNT(*), 4)   AS flagged_rate,
  SUM(f.amount)                                        AS total_volume,
  SUM(IFF(r.is_flagged, f.amount, 0))                 AS flagged_volume
FROM FCT_TRANSACTIONS f
LEFT JOIN FRAUD_RISK_SCORES r ON f.transaction_id = r.transaction_id
GROUP BY f.transaction_date;
