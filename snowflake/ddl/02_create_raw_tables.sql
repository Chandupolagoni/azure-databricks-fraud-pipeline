-- RAW schema: external stage over the ADLS Gen2 `curated/gold` container plus the
-- external table/Snowpipe-ingested copies of the Gold Delta feature and fact tables.

USE SCHEMA FRAUD_PLATFORM.RAW;

CREATE STORAGE INTEGRATION IF NOT EXISTS ADLS_FRAUD_PLATFORM_INT
  TYPE = EXTERNAL_STAGE
  STORAGE_PROVIDER = 'AZURE'
  ENABLED = TRUE
  AZURE_TENANT_ID = '<azure_tenant_id>'
  STORAGE_ALLOWED_LOCATIONS = ('azure://stfraudplatformprod.blob.core.windows.net/curated/');

CREATE FILE FORMAT IF NOT EXISTS PARQUET_DELTA_FORMAT
  TYPE = PARQUET;

CREATE STAGE IF NOT EXISTS STG_CURATED_GOLD
  STORAGE_INTEGRATION = ADLS_FRAUD_PLATFORM_INT
  URL = 'azure://stfraudplatformprod.blob.core.windows.net/curated/gold/'
  FILE_FORMAT = PARQUET_DELTA_FORMAT;

CREATE TABLE IF NOT EXISTS RAW_TRANSACTIONS (
  transaction_id       STRING,
  account_id           STRING,
  card_number_token    STRING,
  merchant_id          STRING,
  merchant_category    STRING,
  amount               NUMBER(18,2),
  currency             STRING,
  transaction_ts       TIMESTAMP_NTZ,
  transaction_date     DATE,
  channel              STRING,
  device_id            STRING,
  ip_address           STRING,
  country_code         STRING,
  _loaded_at           TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);

CREATE TABLE IF NOT EXISTS RAW_FRAUD_FEATURES (
  transaction_id                    STRING,
  account_id                        STRING,
  transaction_date                  DATE,
  txn_count_1h                      NUMBER,
  txn_amount_sum_1h                 NUMBER(18,2),
  txn_count_24h                     NUMBER,
  txn_amount_sum_24h                NUMBER(18,2),
  is_impossible_travel              BOOLEAN,
  distinct_accounts_per_device_24h  NUMBER,
  merchant_risk_score               FLOAT,
  _loaded_at                        TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
);
