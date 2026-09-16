-- Stored procedure: loads/merges the deduped staging stream into the MARTS star schema.

USE SCHEMA FRAUD_PLATFORM.MARTS;

CREATE OR REPLACE PROCEDURE SP_LOAD_FRAUD_MARTS()
RETURNS STRING
LANGUAGE SQL
AS
$$
BEGIN
  MERGE INTO DIM_CUSTOMER tgt
  USING (
    SELECT DISTINCT account_id FROM FRAUD_PLATFORM.STAGING.STRM_RAW_TRANSACTIONS
  ) src
  ON tgt.account_id = src.account_id
  WHEN NOT MATCHED THEN
    INSERT (account_id, onboarding_date, risk_segment)
    VALUES (src.account_id, CURRENT_DATE(), 'UNSCORED');

  MERGE INTO DIM_MERCHANT tgt
  USING (
    SELECT DISTINCT merchant_id, merchant_category FROM FRAUD_PLATFORM.STAGING.STRM_RAW_TRANSACTIONS
  ) src
  ON tgt.merchant_id = src.merchant_id
  WHEN NOT MATCHED THEN
    INSERT (merchant_id, merchant_category, merchant_risk_score)
    VALUES (src.merchant_id, src.merchant_category, 0.5)
  WHEN MATCHED THEN
    UPDATE SET merchant_category = src.merchant_category;

  MERGE INTO FCT_TRANSACTIONS tgt
  USING FRAUD_PLATFORM.STAGING.STRM_RAW_TRANSACTIONS src
  ON tgt.transaction_id = src.transaction_id
  WHEN NOT MATCHED THEN
    INSERT (
      transaction_id, account_id, merchant_id, amount, currency,
      transaction_ts, transaction_date, channel, country_code
    )
    VALUES (
      src.transaction_id, src.account_id, src.merchant_id, src.amount, src.currency,
      src.transaction_ts, src.transaction_date, src.channel, src.country_code
    );

  RETURN 'SP_LOAD_FRAUD_MARTS complete: ' || CURRENT_TIMESTAMP()::STRING;
END;
$$;
