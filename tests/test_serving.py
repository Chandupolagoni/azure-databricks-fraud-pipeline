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
