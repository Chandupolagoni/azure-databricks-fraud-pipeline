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
    y_pred = (np.asarray(y_proba) >= decision_threshold).astype(int)

    precision, recall, _ = precision_recall_curve(y_true, y_proba)
    auc_pr = average_precision_score(y_true, y_proba)
    auc_roc = roc_auc_score(y_true, y_proba)

    tp = int(((y_pred == 1) & (np.asarray(y_true) == 1)).sum())
    fp = int(((y_pred == 1) & (np.asarray(y_true) == 0)).sum())
    fn = int(((y_pred == 0) & (np.asarray(y_true) == 1)).sum())

    precision_at_threshold = tp / (tp + fp) if (tp + fp) else 0.0
    recall_at_threshold = tp / (tp + fn) if (tp + fn) else 0.0

    return {
        "auc_pr": float(auc_pr),
        "auc_roc": float(auc_roc),
        "precision_at_0.5": float(precision_at_threshold),
        "recall_at_0.5": float(recall_at_threshold),
    }
