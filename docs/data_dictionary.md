# Data Dictionary

## Silver: `curated/silver/transactions`

| Column | Type | Description |
|---|---|---|
| transaction_id | string | Unique transaction identifier (business key) |
| account_id | string | Customer account identifier |
| card_number_token | string | SHA-256 tokenized card number (raw PAN never persisted past Bronze) |
| merchant_id | string | Merchant identifier |
| merchant_category | string | Merchant category code (MCC-style grouping) |
| amount | decimal(18,2) | Transaction amount in `currency` |
| currency | string | ISO 4217 currency code |
| transaction_ts | timestamp | Transaction timestamp (UTC) |
| transaction_date | date | Derived date partition column |
| channel | string | `card-present`, `card-not-present`, `digital`, `atm` |
| device_id | string | Device fingerprint (digital channel only) |
| ip_address | string | Client IP (digital channel only) |
| country_code | string | ISO 3166-1 alpha-2 country of transaction |

## Gold: `curated/gold/fraud_features`

| Column | Type | Description |
|---|---|---|
| txn_count_1h / txn_amount_sum_1h | number / decimal | Trailing 1-hour transaction velocity per account |
| txn_count_24h / txn_amount_sum_24h | number / decimal | Trailing 24-hour transaction velocity per account |
| is_impossible_travel | boolean | Country changed faster than physically plausible since prior transaction |
| distinct_accounts_per_device_24h | number | Distinct accounts seen on the same device in trailing 24h (shared-device signal) |
| merchant_risk_score | float | Historical chargeback-rate-derived merchant category risk score (0–1) |

## Snowflake: `MARTS.FCT_TRANSACTIONS`, `MARTS.FRAUD_RISK_SCORES`

See DDL in `snowflake/ddl/04_create_marts.sql` for full column definitions. `FRAUD_RISK_SCORES.p_fraud` is the model's predicted fraud probability (0–1); `is_flagged` is `p_fraud >= 0.5` at the current decision threshold (see `ml/models/model_card.md`).
