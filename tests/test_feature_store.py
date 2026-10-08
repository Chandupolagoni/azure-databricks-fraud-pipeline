import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1] / "ml" / "src"))

from feature_store import (  # noqa: E402
    FEATURE_COLUMNS,
    LABEL_COLUMN,
    load_training_frame,
    make_synthetic_training_frame,
)


def test_synthetic_frame_has_expected_row_count_and_schema():
    df = make_synthetic_training_frame(n_rows=200, seed=1)

    assert len(df) == 200
    assert "transaction_id" in df.columns
    assert LABEL_COLUMN in df.columns
    for column in FEATURE_COLUMNS:
        assert column in df.columns


def test_synthetic_frame_label_is_binary():
    df = make_synthetic_training_frame(n_rows=500, seed=7)

    assert set(df[LABEL_COLUMN].unique()) <= {0, 1}


def test_synthetic_frame_fraud_rate_is_close_to_the_target_quantile():
    df = make_synthetic_training_frame(n_rows=5000, seed=42)

    # The label is thresholded at the 97th percentile of the synthetic fraud score,
    # so roughly 3% of rows should be flagged regardless of seed or sample size.
    fraud_rate = df[LABEL_COLUMN].mean()

    assert 0.01 <= fraud_rate <= 0.05


def test_synthetic_frame_is_deterministic_for_a_fixed_seed():
    first = make_synthetic_training_frame(n_rows=100, seed=5)
    second = make_synthetic_training_frame(n_rows=100, seed=5)

    pd.testing.assert_frame_equal(first, second)


def test_synthetic_frame_differs_across_seeds():
    first = make_synthetic_training_frame(n_rows=200, seed=1)
    second = make_synthetic_training_frame(n_rows=200, seed=2)

    assert not first[LABEL_COLUMN].equals(second[LABEL_COLUMN])


def test_synthetic_frame_transaction_ids_are_unique():
    df = make_synthetic_training_frame(n_rows=300, seed=9)

    assert df["transaction_id"].is_unique


def test_load_training_frame_inner_joins_features_with_labels():
    """load_training_frame should keep only rows present in both Delta tables,
    and only the transaction_id/label columns from the labels table.
    """
    features = pd.DataFrame(
        {
            "transaction_id": ["txn_1", "txn_2", "txn_3"],
            "txn_count_1h": [1, 2, 3],
        }
    )
    labels = pd.DataFrame(
        {
            "transaction_id": ["txn_1", "txn_2", "txn_4"],
            LABEL_COLUMN: [0, 1, 1],
            "label_source": ["chargeback", "chargeback", "manual_review"],
        }
    )

    mock_features_table = MagicMock()
    mock_features_table.to_pandas.return_value = features
    mock_labels_table = MagicMock()
    mock_labels_table.to_pandas.return_value = labels

    with patch(
        "deltalake.DeltaTable", side_effect=[mock_features_table, mock_labels_table]
    ) as mock_delta_table:
        result = load_training_frame("abfss://features/path", "abfss://labels/path")

    assert mock_delta_table.call_args_list == [
        call("abfss://features/path"),
        call("abfss://labels/path"),
    ]
    # txn_3 (no label) and txn_4 (no features) both drop out of the inner join.
    assert list(result["transaction_id"]) == ["txn_1", "txn_2"]
    assert list(result[LABEL_COLUMN]) == [0, 1]
    assert "label_source" not in result.columns


def test_load_training_frame_returns_empty_frame_when_no_ids_overlap():
    features = pd.DataFrame({"transaction_id": ["txn_1"], "txn_count_1h": [1]})
    labels = pd.DataFrame({"transaction_id": ["txn_2"], LABEL_COLUMN: [1]})

    mock_features_table = MagicMock()
    mock_features_table.to_pandas.return_value = features
    mock_labels_table = MagicMock()
    mock_labels_table.to_pandas.return_value = labels

    with patch("deltalake.DeltaTable", side_effect=[mock_features_table, mock_labels_table]):
        result = load_training_frame("features/path", "labels/path")

    assert result.empty
