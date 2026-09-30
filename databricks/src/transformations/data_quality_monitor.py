"""Silver-layer data-quality quarantine-rate monitor.

`cleansing.py::apply_data_quality_rules` already flags failing rows into a
`_dq_passed` column rather than silently dropping them, and `02_silver_transformations.py`
routes them to `transactions_quarantine` for audit. But nothing previously looked at
*how many* rows were quarantined on a given run — a source system quietly breaking
(a schema change, a bad upstream batch) could push the quarantine rate from a normal
sub-1% background rate to 50%+ and the job would still exit 0, because "some rows
failed DQ" was never itself treated as a failure condition.

Mirrors `ml/src/monitor_drift.py`'s shape (threshold + tolerance-free check, alert
message builder, raise-to-fail-the-job hook) so the same `email_notifications.on_failure`
channel already configured on `job_config.json` catches this too, instead of adding a
second alerting path.
"""

from __future__ import annotations

# Background quarantine rate (bad card-present swipes, occasional malformed
# country codes, etc.) normally sits under 1%. Flag once it clears this bar rather
# than on any quarantined row at all.
QUARANTINE_RATE_THRESHOLD = 0.02

# Below this many total rows, a handful of quarantined records can swing the rate
# wildly (5 bad rows out of 20 is 25%) without meaning anything — skip the check
# rather than risk a false alarm on a thin batch, same rationale as
# monitor_drift.py::MIN_RECONCILED_SAMPLES.
MIN_ROWS_FOR_CHECK = 100

MODEL_NAME = "silver-transformations"


def compute_quarantine_rate(passed_count: int, quarantined_count: int) -> float:
    """Fraction of the Silver batch that failed `apply_data_quality_rules`.

    Returns 0.0 for an empty batch rather than dividing by zero — an empty run has
    nothing to quarantine, which isn't itself a quality signal.
    """
    total = passed_count + quarantined_count
    if total == 0:
        return 0.0
    return quarantined_count / total


def check_quarantine_rate_threshold(
    rate: float,
    total_rows: int,
    threshold: float = QUARANTINE_RATE_THRESHOLD,
    min_rows: int = MIN_ROWS_FOR_CHECK,
) -> dict:
    """Compares the batch's quarantine rate against `threshold`.

    `breached=False` on any batch under `min_rows`, regardless of rate, since the
    reading isn't trustworthy yet — same skip-on-thin-sample rationale as the live
    drift monitor.
    """
    breached = total_rows >= min_rows and rate > threshold
    return {
        "rate": round(rate, 4),
        "threshold": threshold,
        "total_rows": total_rows,
        "min_rows": min_rows,
        "breached": breached,
    }


def build_dq_alert_message(check_result: dict, passed_count: int, quarantined_count: int) -> str:
    """Formats the on-call-facing alert body, matching the tone of
    `monitor_drift.py::build_drift_alert_message`.
    """
    return (
        f"[{MODEL_NAME}] Silver data-quality quarantine rate exceeded threshold\n"
        f"  Quarantine rate: {check_result['rate']:.2%} (threshold: {check_result['threshold']:.2%})\n"
        f"  Rows passed: {passed_count} | quarantined: {quarantined_count} "
        f"(total: {check_result['total_rows']})\n"
        f"  Action: check `transactions_quarantine` for the failing rule(s) "
        f"(amount/id nulls, non-positive amount, malformed country_code) and confirm "
        f"whether an upstream source changed shape before re-running."
    )


class DataQualityAlertError(RuntimeError):
    """Raised by `raise_if_quarantine_rate_breached` to fail the run when the
    quarantine rate clears the threshold, so the Databricks job task exits non-zero
    and trips `job_config.json`'s `email_notifications.on_failure` channel — the same
    alerting path already used for ETL task failures and live model drift.
    """


def raise_if_quarantine_rate_breached(
    check_result: dict, passed_count: int, quarantined_count: int
) -> None:
    """Fails the run with the formatted alert body when `check_result["breached"]`
    is True. A no-op otherwise, so a clean or thin-batch run exits 0 as normal.
    """
    if not check_result["breached"]:
        return

    raise DataQualityAlertError(
        build_dq_alert_message(check_result, passed_count, quarantined_count)
    )
