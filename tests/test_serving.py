import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "ml" / "src"))

pytest.importorskip("databricks.sdk")

from serving import (  # noqa: E402
    ENDPOINT_NAME,
    SERVED_ENTITY_NAME,
    build_endpoint_config,
    build_scoring_payload,
    deploy_serving_endpoint,
    score_transaction,
    wait_until_ready,
)


def test_build_endpoint_config_points_at_requested_version():
    config = build_endpoint_config(model_version="7", scale_to_zero=True)

    entity = config.served_entities[0]
    assert entity.entity_version == "7"
    assert entity.name == SERVED_ENTITY_NAME
    assert entity.scale_to_zero_enabled is True
    assert config.traffic_config.routes[0].traffic_percentage == 100


def test_build_scoring_payload_orders_by_feature_columns():
    from feature_store import FEATURE_COLUMNS

    features = {col: idx for idx, col in enumerate(FEATURE_COLUMNS)}
    payload = build_scoring_payload(features)

    assert list(payload["dataframe_records"][0].keys()) == FEATURE_COLUMNS


def test_build_scoring_payload_raises_on_missing_feature():
    with pytest.raises(ValueError, match="txn_count_1h"):
        build_scoring_payload({})


def test_deploy_creates_endpoint_when_absent():
    client = MagicMock()
    client.serving_endpoints.list.return_value = []

    deploy_serving_endpoint(client, model_version="3")

    client.serving_endpoints.create.assert_called_once()
    assert client.serving_endpoints.create.call_args.kwargs["name"] == ENDPOINT_NAME
    client.serving_endpoints.update_config.assert_not_called()


def test_deploy_updates_endpoint_when_present():
    client = MagicMock()
    existing = MagicMock()
    existing.name = ENDPOINT_NAME
    client.serving_endpoints.list.return_value = [existing]

    deploy_serving_endpoint(client, model_version="4")

    client.serving_endpoints.update_config.assert_called_once()
    client.serving_endpoints.create.assert_not_called()


def test_wait_until_ready_returns_status_once_ready(monkeypatch):
    client = MagicMock()
    ready_status = MagicMock()
    ready_status.state.ready = "READY"
    client.serving_endpoints.get.return_value = ready_status
    monkeypatch.setattr("serving.time.sleep", lambda seconds: None)

    result = wait_until_ready(client, timeout_seconds=30, poll_seconds=1)

    assert result is ready_status
    client.serving_endpoints.get.assert_called_with(ENDPOINT_NAME)


def test_wait_until_ready_polls_until_ready(monkeypatch):
    client = MagicMock()
    not_ready = MagicMock()
    not_ready.state.ready = "NOT_READY"
    ready = MagicMock()
    ready.state.ready = "READY"
    client.serving_endpoints.get.side_effect = [not_ready, not_ready, ready]

    sleep_calls = []
    monkeypatch.setattr("serving.time.sleep", lambda seconds: sleep_calls.append(seconds))

    result = wait_until_ready(client, timeout_seconds=30, poll_seconds=2)

    assert result is ready
    assert sleep_calls == [2, 2]
    assert client.serving_endpoints.get.call_count == 3


def test_wait_until_ready_raises_timeout_error_when_never_ready():
    client = MagicMock()
    not_ready = MagicMock()
    not_ready.state.ready = "NOT_READY"
    client.serving_endpoints.get.return_value = not_ready

    with pytest.raises(TimeoutError, match=ENDPOINT_NAME):
        wait_until_ready(client, timeout_seconds=0, poll_seconds=0)


def test_score_transaction_flags_when_prediction_above_threshold():
    from feature_store import FEATURE_COLUMNS

    client = MagicMock()
    response = MagicMock()
    response.predictions = [0.87]
    client.serving_endpoints.query.return_value = response

    features = {col: 1.0 for col in FEATURE_COLUMNS}
    result = score_transaction(client, features, flag_threshold=0.5)

    assert result == {"p_fraud": 0.87, "is_flagged": True}
    call_kwargs = client.serving_endpoints.query.call_args.kwargs
    assert call_kwargs["name"] == ENDPOINT_NAME


def test_score_transaction_not_flagged_when_prediction_below_threshold():
    from feature_store import FEATURE_COLUMNS

    client = MagicMock()
    response = MagicMock()
    response.predictions = [0.2]
    client.serving_endpoints.query.return_value = response

    features = {col: 1.0 for col in FEATURE_COLUMNS}
    result = score_transaction(client, features, flag_threshold=0.5)

    assert result == {"p_fraud": 0.2, "is_flagged": False}


def test_score_transaction_raises_on_missing_feature():
    client = MagicMock()

    with pytest.raises(ValueError, match="txn_count_1h"):
        score_transaction(client, {})
