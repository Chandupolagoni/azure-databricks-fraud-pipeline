"""Deploy (create-or-update) the Databricks job configs under databricks/jobs/ via the
Jobs API, so the committed JSON job configs are always in sync with the workspace
instead of only being applied by hand (see docs/runbook.md's old "Databricks workspace
bootstrap" step). Run from CI on every push to main that touches a job config.

Idempotent by design: looks each job up by its `name` field via `jobs/list`, and does a
`jobs/reset` if it already exists or a `jobs/create` if it doesn't, so re-running on every
push to main updates the existing job in place instead of creating a duplicate.

Usage:
    DATABRICKS_HOST=https://adb-xxxx.azuredatabricks.net \
    DATABRICKS_TOKEN=... \
    DATABRICKS_CLUSTER_POLICY_ID=... \
    DATABRICKS_STORAGE_ACCOUNT=stfraudplatformdev \
    python scripts/deploy_databricks_jobs.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

JOBS_DIR = Path(__file__).resolve().parent.parent / "databricks" / "jobs"

# Template placeholders that appear in the committed job config JSON -> the env var
# that supplies the real value at deploy time (kept out of the repo on purpose).
TEMPLATE_VARS = {
    "{{cluster_policy_id}}": "DATABRICKS_CLUSTER_POLICY_ID",
    "{{storage_account}}": "DATABRICKS_STORAGE_ACCOUNT",
}


def render_job_config(raw_text: str, env: dict[str, str] | None = None) -> dict[str, Any]:
    """Substitute `{{placeholder}}` tokens in a job config file with env var values.

    Raises if a placeholder is present in the file but its env var isn't set, rather than
    silently deploying a job with a literal `{{cluster_policy_id}}` string in it.
    """
    env = env if env is not None else os.environ
    rendered = raw_text
    for placeholder, env_var in TEMPLATE_VARS.items():
        if placeholder in rendered:
            value = env.get(env_var)
            if not value:
                raise RuntimeError(f"{env_var} is not set but {placeholder} appears in the job config")
            rendered = rendered.replace(placeholder, value)
    return json.loads(rendered)


def find_existing_job_id(host: str, token: str, job_name: str) -> int | None:
    """Look up a job by its `name` field via `jobs/list`.

    Job names aren't unique in the Jobs API, but this platform only ever deploys the
    small, fixed set of jobs under databricks/jobs/, so the first exact-name match is
    the right one.
    """
    resp = requests.get(
        f"{host}/api/2.1/jobs/list",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 25, "name": job_name},
        timeout=30,
    )
    resp.raise_for_status()
    for job in resp.json().get("jobs", []):
        if job["settings"]["name"] == job_name:
            return job["job_id"]
    return None


def deploy_job(host: str, token: str, job_config: dict[str, Any]) -> int:
    """Create the job if it doesn't exist yet, otherwise reset it in place to match the
    committed config. Returns the job_id either way."""
    job_name = job_config["name"]
    existing_id = find_existing_job_id(host, token, job_name)
    headers = {"Authorization": f"Bearer {token}"}

    if existing_id is None:
        resp = requests.post(f"{host}/api/2.1/jobs/create", headers=headers, json=job_config, timeout=30)
        resp.raise_for_status()
        job_id = resp.json()["job_id"]
        print(f"created job '{job_name}' (job_id={job_id})")
        return job_id

    resp = requests.post(
        f"{host}/api/2.1/jobs/reset",
        headers=headers,
        json={"job_id": existing_id, "new_settings": job_config},
        timeout=30,
    )
    resp.raise_for_status()
    print(f"updated job '{job_name}' (job_id={existing_id})")
    return existing_id


def main() -> int:
    host = os.environ.get("DATABRICKS_HOST", "").rstrip("/")
    token = os.environ.get("DATABRICKS_TOKEN", "")
    if not host or not token:
        print("DATABRICKS_HOST and DATABRICKS_TOKEN must both be set", file=sys.stderr)
        return 1

    config_files = sorted(JOBS_DIR.glob("*.json"))
    if not config_files:
        print(f"no job config files found under {JOBS_DIR}", file=sys.stderr)
        return 1

    for config_path in config_files:
        job_config = render_job_config(config_path.read_text())
        deploy_job(host, token, job_config)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
