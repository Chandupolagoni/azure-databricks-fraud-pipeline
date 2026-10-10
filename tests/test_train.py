import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "ml" / "src"))

import train  # noqa: E402
from feature_store import FEATURE_COLUMNS, LABEL_COLUMN  # noqa: E402
from train import MODEL_NAME, PROMOTION_AUC_PR_THRESHOLD  # noqa: E402


def _training_frame(n: int = 20) -> pd.DataFrame:
    """A tiny, balanced, deterministic frame - just enough rows for
    `train_test_split`'s `stratify` to find both classes in every split.
    """
    data = {col: np.linspace(0, 1, n) for col in FEATURE_COLUMNS}
    data[LABEL_COLUMN] = [i % 2 for i in range(n)]
    data["transaction_id"] = [f"txn_{i}" for i in range(n)]
    return pd.DataFrame(data)


def _mock_mlflow(latest_version: str = "3"):
    """Stubs the whole `mlflow` module reference `train.py` imports, for the same
    reason `test_inference.py` does for `inference.py`: `mlflow.sklearn` is a
    lazy-loading proxy that re-resolves on every attribute access, so patching
    `mlflow.sklearn.log_model` directly doesn't reliably stick across the call
    inside `train()`.
    """
    fake_run = MagicMock()
    fake_run.info.run_id = "run-123"
    fake_mlflow = MagicMock()
    fake_mlflow.start_run.return_value.__enter__.return_value = fake_run

    fake_version = MagicMock()
    fake_version.version = latest_version
    fake_client = MagicMock()
    fake_client.get_latest_versions.return_value = [fake_version]
    fake_mlflow.tracking.MlflowClient.return_value = fake_client

    return fake_mlflow, fake_client


def _mock_model_class(n_test_rows: int = 4):
    """A stand-in `GradientBoostingClassifier` class: instantiating it returns a
    fake "fitted" model whose `predict_proba` the test controls directly, instead
    of paying for a real `fit()` on every test run.
    """
    fake_model = MagicMock()
    fake_model.predict_proba.return_value = np.zeros((n_test_rows, 2))
    fake_model_class = MagicMock(return_value=fake_model)
    return fake_model_class, fake_model


def _run_train(metrics, use_synthetic=True, delta_path=None, labels_path=None):
    fake_mlflow, fake_client = _mock_mlflow()
    fake_model_class, fake_model = _mock_model_class()

    with (
        patch.object(train, "mlflow", fake_mlflow),
        patch.object(train, "GradientBoostingClassifier", fake_model_class),
        patch.object(train, "make_synthetic_training_frame", return_value=_training_frame()),
        patch.object(train, "evaluate_predictions", return_value=metrics),
    ):
        train.train(delta_path, labels_path, use_synthetic)

    return fake_mlflow, fake_client, fake_model


def test_train_promotes_model_when_auc_pr_clears_threshold():
    metrics = {
        "auc_pr": PROMOTION_AUC_PR_THRESHOLD + 0.1,
        "auc_roc": 0.9,
        "precision_at_0.5": 0.8,
        "recall_at_0.5": 0.7,
    }
    _, fake_client, _ = _run_train(metrics)

    fake_client.transition_model_version_stage.assert_called_once_with(
        name=MODEL_NAME, version="3", stage="Staging"
    )


def test_train_does_not_promote_model_below_threshold():
    metrics = {
        "auc_pr": PROMOTION_AUC_PR_THRESHOLD - 0.1,
        "auc_roc": 0.5,
        "precision_at_0.5": 0.2,
        "recall_at_0.5": 0.1,
    }
    _, fake_client, _ = _run_train(metrics)

    fake_client.transition_model_version_stage.assert_not_called()


def test_train_promotion_gate_includes_the_threshold_itself():
    """The gate is `>=`, not `>`: an auc_pr exactly at the threshold still promotes."""
    metrics = {
        "auc_pr": PROMOTION_AUC_PR_THRESHOLD,
        "auc_roc": 0.5,
        "precision_at_0.5": 0.2,
        "recall_at_0.5": 0.1,
    }
    _, fake_client, _ = _run_train(metrics)

    fake_client.transition_model_version_stage.assert_called_once()


def test_train_logs_params_metrics_and_registers_model():
    metrics = {
        "auc_pr": 0.9,
        "auc_roc": 0.9,
        "precision_at_0.5": 0.8,
        "recall_at_0.5": 0.7,
    }
    fake_mlflow, _, fake_model = _run_train(metrics)

    fake_mlflow.log_params.assert_called_once_with(
        {
            "n_estimators": 300,
            "max_depth": 4,
            "learning_rate": 0.05,
            "subsample": 0.8,
            "random_state": 42,
        }
    )
    fake_mlflow.log_metrics.assert_called_once_with(metrics)
    fake_mlflow.sklearn.log_model.assert_called_once_with(
        fake_model, artifact_path="model", registered_model_name=MODEL_NAME
    )


def test_train_uses_synthetic_frame_when_requested():
    metrics = {"auc_pr": 0.9, "auc_roc": 0.9, "precision_at_0.5": 0.8, "recall_at_0.5": 0.7}
    fake_mlflow, _fake_client = _mock_mlflow()
    fake_model_class, _ = _mock_model_class()
    fake_synthetic = MagicMock(return_value=_training_frame())
    fake_loader = MagicMock()

    with (
        patch.object(train, "mlflow", fake_mlflow),
        patch.object(train, "GradientBoostingClassifier", fake_model_class),
        patch.object(train, "make_synthetic_training_frame", fake_synthetic),
        patch.object(train, "load_training_frame", fake_loader),
        patch.object(train, "evaluate_predictions", return_value=metrics),
    ):
        train.train(None, None, True)

    fake_synthetic.assert_called_once()
    fake_loader.assert_not_called()


def test_train_uses_delta_loader_when_not_synthetic():
    metrics = {"auc_pr": 0.9, "auc_roc": 0.9, "precision_at_0.5": 0.8, "recall_at_0.5": 0.7}
    fake_mlflow, _fake_client = _mock_mlflow()
    fake_model_class, _ = _mock_model_class()
    fake_synthetic = MagicMock()
    fake_loader = MagicMock(return_value=_training_frame())

    with (
        patch.object(train, "mlflow", fake_mlflow),
        patch.object(train, "GradientBoostingClassifier", fake_model_class),
        patch.object(train, "make_synthetic_training_frame", fake_synthetic),
        patch.object(train, "load_training_frame", fake_loader),
        patch.object(train, "evaluate_predictions", return_value=metrics),
    ):
        train.train("/delta/features", "/delta/labels", False)

    fake_loader.assert_called_once_with("/delta/features", "/delta/labels")
    fake_synthetic.assert_not_called()
