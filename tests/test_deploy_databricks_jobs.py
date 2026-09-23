import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))

from deploy_databricks_jobs import (  # noqa: E402
    deploy_job,
    find_existing_job_id,
    render_job_config,
)


def test_render_job_config_substitutes_known_placeholders():
    raw = json.dumps({"name": "x", "cluster": "{{cluster_policy_id}}", "acct": "{{storage_account}}"})
    env = {"DATABRICKS_CLUSTER_POLICY_ID": "policy-123", "DATABRICKS_STORAGE_ACCOUNT": "sadatalake"}

    rendered = render_job_config(raw, env=env)

    assert rendered["cluster"] == "policy-123"
    assert rendered["acct"] == "sadatalake"


def test_render_job_config_raises_on_missing_env_var():
    raw = json.dumps({"name": "x", "cluster": "{{cluster_policy_id}}"})

    with pytest.raises(RuntimeError, match="DATABRICKS_CLUSTER_POLICY_ID"):
        render_job_config(raw, env={})


def test_render_job_config_is_a_noop_without_placeholders():
    raw = json.dumps({"name": "x", "schedule": {"quartz_cron_expression": "0 0 5 * * ?"}})

    assert render_job_config(raw, env={}) == json.loads(raw)


@patch("deploy_databricks_jobs.requests.get")
def test_find_existing_job_id_matches_by_exact_name(mock_get):
    mock_get.return_value = MagicMock(
        json=lambda: {"jobs": [{"job_id": 42, "settings": {"name": "fraud-platform-medallion-etl"}}]}
    )
    mock_get.return_value.raise_for_status = lambda: None

    job_id = find_existing_job_id("https://host", "tok", "fraud-platform-medallion-etl")

    assert job_id == 42


@patch("deploy_databricks_jobs.requests.get")
def test_find_existing_job_id_returns_none_when_absent(mock_get):
    mock_get.return_value = MagicMock(json=lambda: {"jobs": []})
    mock_get.return_value.raise_for_status = lambda: None

    assert find_existing_job_id("https://host", "tok", "missing-job") is None


@patch("deploy_databricks_jobs.find_existing_job_id", return_value=None)
@patch("deploy_databricks_jobs.requests.post")
def test_deploy_job_creates_when_absent(mock_post, mock_find):
    mock_post.return_value = MagicMock(json=lambda: {"job_id": 99})
    mock_post.return_value.raise_for_status = lambda: None

    job_id = deploy_job("https://host", "tok", {"name": "new-job"})

    assert job_id == 99
    assert mock_post.call_args.args[0].endswith("/jobs/create")


@patch("deploy_databricks_jobs.find_existing_job_id", return_value=42)
@patch("deploy_databricks_jobs.requests.post")
def test_deploy_job_resets_when_present(mock_post, mock_find):
    mock_post.return_value = MagicMock(json=lambda: {})
    mock_post.return_value.raise_for_status = lambda: None

    job_id = deploy_job("https://host", "tok", {"name": "existing-job"})

    assert job_id == 42
    assert mock_post.call_args.args[0].endswith("/jobs/reset")
    assert mock_post.call_args.kwargs["json"]["job_id"] == 42
