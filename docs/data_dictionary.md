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

## Snowflake: `MARTS.VW_MERCHANT_RISK_SUMMARY`, `MARTS.VW_MERCHANT_RISK_TRIAGE_QUEUE`

Per-merchant rollup joining the static `DIM_MERCHANT.merchant_risk_score` against a rolling
trailing-30-day flagged rate computed from `FCT_TRANSACTIONS`/`FRAUD_RISK_SCORES`. See DDL in
`snowflake/ddl/06_create_merchant_risk_view.sql`.

| Column | Type | Description |
|---|---|---|
| historical_risk_score | float | Static, offline-recomputed `DIM_MERCHANT.merchant_risk_score` |
| flagged_rate_30d | float | Trailing 30-day share of this merchant's transactions flagged by the model |
| risk_score_divergence | float | `flagged_rate_30d - historical_risk_score`; large positive values mean live risk has outrun the static score |
| risk_tier | string | `INSUFFICIENT_VOLUME` (<20 txns in window), `NORMAL`, `ELEVATED` (>=0.03), or `HIGH` (>=0.10) flagged rate |

`VW_MERCHANT_RISK_TRIAGE_QUEUE` is `VW_MERCHANT_RISK_SUMMARY` filtered to `ELEVATED`/`HIGH` and
sorted worst-first — see `docs/runbook.md`'s Daily operation section.

## Snowflake: `RAW.RAW_CHARGEBACK_OUTCOMES`, `MARTS.CONFIRMED_FRAUD_OUTCOMES`

Card-network chargeback/dispute settlement feed and the ground-truth table it reconciles into.
See DDL in `snowflake/ddl/07_create_chargeback_outcomes_feed.sql` and
`snowflake/ddl/05_create_fraud_outcomes.sql`, and the merge logic in
`snowflake/procedures/sp_reconcile_fraud_outcomes.sql`.

| Column | Type | Description |
|---|---|---|
| network | string | Card network that filed the dispute (`VISA`, `MASTERCARD`, `AMEX`, `DISCOVER`) |
| outcome | string | Dispute resolution (`MERCHANT_WON`, `MERCHANT_LOST`, `WITHDRAWN`) — not itself a fraud signal |
| is_fraud_confirmed | boolean | Issuer-confirmed fraud outcome, distinct from a non-fraud dispute such as a billing error |
| resolved_at | timestamp | When the issuer closed out the dispute; `NULL` while still open |
| outcome_source (MARTS) | string | `'chargeback:<network>'` for every row reconciled through this feed |

`CONFIRMED_FRAUD_OUTCOMES` only gains a row once a transaction both exists in
`FCT_TRANSACTIONS` and has a `resolved_at` chargeback outcome — see `docs/runbook.md`'s Daily
operation section for the reconciliation cadence.
