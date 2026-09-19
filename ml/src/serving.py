"""Wires the registered `fraud-risk-classifier` model to a Databricks Model Serving
endpoint for real-time (synchronous, sub-second) fraud scoring at authorization time.

This closes the "real-time path (documented, not deployed here) would front the
registered model with a Databricks Model Serving endpoint" gap noted in
architecture.md and in `inference.py`'s module docstring — the batch path in
`inference.py` still owns the offline/backfill scoring job; this module owns the
low-latency online path in front of the same registered model.

Uses the Databricks SDK (`databricks-sdk`) so it runs both from a Databricks job/
notebook (with an implicit auth context) and from a CI/CD deploy step against an
explicit workspace host + token.
"""

from __future__ import annotations

import time

from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import EndpointCoreConfigInput, Route, ServedEntityInput, TrafficConfig

MODEL_NAME = "fraud-risk-classifier"
ENDPOINT_NAME = "fraud-risk-classifier-endpoint"
SERVED_ENTITY_NAME = "fraud-risk-classifier-current"
WORKLOAD_SIZE = "Small"  # 0-4 concurrent requests; bump for higher authorization-time load


def build_endpoint_config(model_version: str, scale_to_zero: bool = True) -> EndpointCoreConfigInput:
    """Builds the serving config for a given Production model version.

    Kept as a pure function (no client calls) so the config shape is unit-testable
    without a live workspace.
    """
    served_entity = ServedEntityInput(
        name=SERVED_ENTITY_NAME,
        entity_name=MODEL_NAME,
        entity_version=model_version,
        workload_size=WORKLOAD_SIZE,
        scale_to_zero_enabled=scale_to_zero,
    )
    return EndpointCoreConfigInput(
        served_entities=[served_entity],
        traffic_config=TrafficConfig(
            routes=[Route(served_model_name=SERVED_ENTITY_NAME, traffic_percentage=100)]
        ),
    )


def deploy_serving_endpoint(client: WorkspaceClient, model_version: str, scale_to_zero: bool = True):
    """Creates the endpoint if it doesn't exist yet, otherwise updates it to point at
    `model_version` — the standard promote-to-Production -> redeploy flow, meant to
    run right after `train.py` promotes a version to `Production` in the Registry.
    """
    config = build_endpoint_config(model_version, scale_to_zero=scale_to_zero)

    existing_names = {ep.name for ep in client.serving_endpoints.list()}
    if ENDPOINT_NAME in existing_names:
        return client.serving_endpoints.update_config(
            name=ENDPOINT_NAME,
            served_entities=config.served_entities,
            traffic_config=config.traffic_config,
        )
    return client.serving_endpoints.create(name=ENDPOINT_NAME, config=config)


def wait_until_ready(client: WorkspaceClient, timeout_seconds: int = 900, poll_seconds: int = 15):
    """Polls until the endpoint's config update finishes (state.ready == 'READY'), or
    raises on timeout. Deploy scripts should call this before flipping any downstream
    caller over to the new version.
    """
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = client.serving_endpoints.get(ENDPOINT_NAME)
        if status.state and status.state.ready == "READY":
            return status
        time.sleep(poll_seconds)
    raise TimeoutError(f"Endpoint {ENDPOINT_NAME} not READY after {timeout_seconds}s")


def build_scoring_payload(features: dict) -> dict:
    """Builds the request body for a synchronous scoring call, in the column
    orientation the served sklearn model expects. `features` maps each of
    `feature_store.FEATURE_COLUMNS` to its value for one transaction.
    """
    from feature_store import FEATURE_COLUMNS

    missing = [col for col in FEATURE_COLUMNS if col not in features]
    if missing:
        raise ValueError(f"Missing required features for scoring: {missing}")

    return {"dataframe_records": [{col: features[col] for col in FEATURE_COLUMNS}]}


def score_transaction(client: WorkspaceClient, features: dict, flag_threshold: float = 0.5) -> dict:
    """Synchronous real-time scoring call for use at authorization time — the
    low-latency counterpart to the batch path in `inference.py::score_batch`.
    """
    payload = build_scoring_payload(features)
    response = client.serving_endpoints.query(
        name=ENDPOINT_NAME, dataframe_records=payload["dataframe_records"]
    )
    p_fraud = response.predictions[0]
    return {"p_fraud": p_fraud, "is_flagged": p_fraud >= flag_threshold}
