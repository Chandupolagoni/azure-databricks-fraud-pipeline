import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "ml" / "src"))

import inference  # noqa: E402
from feature_store import FEATURE_COLUMNS  # noqa: E402
from inference import FLAG_THRESHOLD, MODEL_NAME, score_batch, write_scores_to_snowflake  # noqa: E402


def _features_frame(n: int = 4) -> pd.DataFrame:
    data = {col: np.linspace(0, 1, n) for col in FEATURE_COLUMNS}
    data["transaction_id"] = [f"txn_{i}" for i in range(n)]
    return pd.DataFrame(data)


def _mock_mlflow(predict_proba_return):
    """Stubs the whole `mlflow` module reference `inference.py` imports, rather than
    patching `mlflow.sklearn.load_model` directly: `mlflow.sklearn` is a lazy-loading
    proxy that re-resolves on every attribute access, so a patch of its `load_model`
    attribute doesn't reliably stick across the call inside `score_batch`.
    """
    fake_model = MagicMock()
    fake_model.predict_proba.return_value = predict_proba_return
    fake_mlflow = MagicMock()
    fake_mlflow.sklearn.load_model.return_value = fake_model
    return fake_mlflow


def test_score_batch_loads_model_from_requested_stage():
    features = _features_frame()
    fake_mlflow = _mock_mlflow(np.zeros((len(features), 2)))

    with patch.object(inference, "mlflow", fake_mlflow):
        score_batch(features, stage="Staging")

    fake_mlflow.sklearn.load_model.assert_called_once_with(f"models:/{MODEL_NAME}/Staging")


def test_score_batch_defaults_to_production_stage():
    features = _features_frame()
    fake_mlflow = _mock_mlflow(np.zeros((len(features), 2)))

    with patch.object(inference, "mlflow", fake_mlflow):
        score_batch(features)

    fake_mlflow.sklearn.load_model.assert_called_once_with(f"models:/{MODEL_NAME}/Production")


def test_score_batch_scores_only_the_fraud_probability_column():
    features = _features_frame(n=3)
    # predict_proba's column 0 is P(not fraud), column 1 is P(fraud) - score_batch
    # must take column 1, not column 0.
    fake_mlflow = _mock_mlflow(np.array([[0.9, 0.1], [0.5, 0.5], [0.2, 0.8]]))

    with patch.object(inference, "mlflow", fake_mlflow):
        scored = score_batch(features)

    assert list(scored["p_fraud"]) == pytest.approx([0.1, 0.5, 0.8])


def test_score_batch_flags_at_threshold():
    features = _features_frame(n=3)
    fake_mlflow = _mock_mlflow(
        np.array([[1 - 0.1, 0.1], [1 - FLAG_THRESHOLD, FLAG_THRESHOLD], [1 - 0.9, 0.9]])
    )

    with patch.object(inference, "mlflow", fake_mlflow):
        scored = score_batch(features)

    assert list(scored["is_flagged"]) == [False, True, True]


def test_score_batch_passes_only_feature_columns_to_model():
    features = _features_frame(n=2)
    features["some_other_non_feature_column"] = ["a", "b"]
    fake_mlflow = _mock_mlflow(np.zeros((2, 2)))

    with patch.object(inference, "mlflow", fake_mlflow):
        score_batch(features)

    called_with = fake_mlflow.sklearn.load_model.return_value.predict_proba.call_args[0][0]
    assert list(called_with.columns) == FEATURE_COLUMNS


def test_score_batch_preserves_transaction_id_order_and_output_columns():
    features = _features_frame(n=3)
    fake_mlflow = _mock_mlflow(np.zeros((3, 2)))

    with patch.object(inference, "mlflow", fake_mlflow):
        scored = score_batch(features, stage="Production")

    assert list(scored.columns) == ["transaction_id", "model_version", "p_fraud", "is_flagged"]
    assert list(scored["transaction_id"]) == list(features["transaction_id"])
    assert (scored["model_version"] == "Production").all()


def test_write_scores_to_snowflake_writes_to_marts_fraud_risk_scores_table():
    scores = pd.DataFrame(
        {
            "transaction_id": ["txn_0"],
            "model_version": ["Production"],
            "p_fraud": [0.42],
            "is_flagged": [False],
        }
    )
    fake_conn = MagicMock()
    fake_connect = MagicMock()
    fake_connect.return_value.__enter__.return_value = fake_conn

    with (
        patch("snowflake.connector.connect", fake_connect),
        patch("snowflake.connector.pandas_tools.write_pandas") as write_pandas,
    ):
        write_scores_to_snowflake(scores, connection_params={"account": "xyz"})

    fake_connect.assert_called_once_with(account="xyz")
    write_pandas.assert_called_once()
    args, kwargs = write_pandas.call_args
    assert args[0] is fake_conn
    assert args[1] is scores
    assert kwargs["table_name"] == "FRAUD_RISK_SCORES"
    assert kwargs["schema"] == "MARTS"
