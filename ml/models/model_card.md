# Model Card — Fraud Risk Classifier

## Overview
- **Model type:** Gradient-boosted decision tree classifier (`sklearn.ensemble.GradientBoostingClassifier`; production variant swaps in XGBoost/LightGBM for training-time performance at scale)
- **Task:** Binary classification — probability a card transaction is fraudulent (`p_fraud`)
- **Registry name:** `fraud-risk-classifier` (MLflow Model Registry)

## Training data
- Source: Gold `fraud_features` table (`databricks/notebooks/04_feature_engineering.py`), joined with historical confirmed-fraud outcomes
- Features: transaction velocity (1h/24h), impossible-travel geo signal, device-reuse count, merchant category risk score — see `ml/src/feature_store.py::FEATURE_COLUMNS`
- Label: `is_fraud` — confirmed chargebacks/fraud-ops case outcomes, joined on `transaction_id`
- Class balance: heavily imbalanced (fraud is a low base-rate event); evaluated on AUC-PR rather than accuracy/AUC-ROC alone

## Evaluation
- Primary metric: **AUC-PR** (average precision) — promotion gate at `>= 0.55` (`ml/src/train.py::PROMOTION_AUC_PR_THRESHOLD`)
- Secondary: AUC-ROC, precision/recall at the 0.5 decision threshold
- See `ml/src/evaluate.py` for the full metric implementation

## Intended use
Batch and (documented, not deployed here) real-time scoring to flag transactions for fraud-ops review. **This is a decision-support signal, not an automated block/approve system** — flagged transactions route to `FRAUD_OPS` case queues (`snowflake/ddl/04_create_marts.sql::FRAUD_RISK_SCORES`).

## Limitations & risks
- Trained on synthetic/sample data in this reference repo; a production deployment requires periodic retraining as fraud patterns drift, and fairness/bias review across customer segments before deployment
- Feature set does not include free-text or unstructured signals (e.g. merchant descriptors); could be extended with an embedding-based feature
- Decision threshold (0.5) is a starting point — should be tuned against fraud-ops review capacity and cost-of-false-positive analysis

## Promotion lifecycle
`None` → `Staging` (automatic, on passing the AUC-PR gate in `train.py`) → `Production` (manual promotion after fraud-ops review of a holdout sample) → `Archived` (superseded versions)
