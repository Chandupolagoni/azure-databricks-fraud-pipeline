"""Evaluation metrics for the fraud classifier.

Precision/recall/AUC-PR are used (rather than plain accuracy/AUC-ROC) because fraud
is a heavily imbalanced label — AUC-PR is far more informative at low base rates.
"""

import numpy as np
from sklearn.metrics import (
    average_precision_score,
    precision_recall_curve,
    roc_auc_score,
)


def evaluate_predictions(y_true, y_proba, decision_threshold: float = 0.5) -> dict:
    """Compute AUC-PR/AUC-ROC and precision/recall at a decision threshold.

    Both `train.py`'s promotion gate and `monitor_drift.py`'s live drift check feed this
    function results assembled from a query (a train/test split, a reconciled Snowflake
    window). Validating the shapes here turns a malformed upstream result into a clear
    `ValueError` at the call site instead of an opaque `sklearn`/`numpy` broadcast error
    surfacing several frames deeper.
    """
    y_true_arr = np.asarray(y_true)
    y_proba_arr = np.asarray(y_proba)

    if y_true_arr.shape[0] == 0 or y_proba_arr.shape[0] == 0:
        raise ValueError(
            "evaluate_predictions requires at least one sample; got an empty y_true/y_proba"
        )
    if y_true_arr.shape[0] != y_proba_arr.shape[0]:
        raise ValueError(
            "y_true and y_proba must be the same length, got "
            f"{y_true_arr.shape[0]} and {y_proba_arr.shape[0]}"
        )
    if not 0.0 <= decision_threshold <= 1.0:
        raise ValueError(f"decision_threshold must be between 0.0 and 1.0, got {decision_threshold}")

    y_pred = (y_proba_arr >= decision_threshold).astype(int)

    precision, recall, _ = precision_recall_curve(y_true_arr, y_proba_arr)
    auc_pr = average_precision_score(y_true_arr, y_proba_arr)
    auc_roc = roc_auc_score(y_true_arr, y_proba_arr)

    tp = int(((y_pred == 1) & (y_true_arr == 1)).sum())
    fp = int(((y_pred == 1) & (y_true_arr == 0)).sum())
    fn = int(((y_pred == 0) & (y_true_arr == 1)).sum())

    precision_at_threshold = tp / (tp + fp) if (tp + fp) else 0.0
    recall_at_threshold = tp / (tp + fn) if (tp + fn) else 0.0

    return {
        "auc_pr": float(auc_pr),
        "auc_roc": float(auc_roc),
        "precision_at_0.5": float(precision_at_threshold),
        "recall_at_0.5": float(recall_at_threshold),
    }
