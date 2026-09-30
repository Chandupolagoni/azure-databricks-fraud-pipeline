import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "databricks" / "src"))

from transformations.data_quality_monitor import (  # noqa: E402
    MIN_ROWS_FOR_CHECK,
    QUARANTINE_RATE_THRESHOLD,
    DataQualityAlertError,
    build_dq_alert_message,
    check_quarantine_rate_threshold,
    compute_quarantine_rate,
    raise_if_quarantine_rate_breached,
)


def test_compute_quarantine_rate_basic():
    assert compute_quarantine_rate(passed_count=90, quarantined_count=10) == pytest.approx(0.1)


def test_compute_quarantine_rate_empty_batch_is_zero():
    assert compute_quarantine_rate(passed_count=0, quarantined_count=0) == 0.0


def test_check_quarantine_rate_threshold_not_breached_below_threshold():
    rate = compute_quarantine_rate(passed_count=990, quarantined_count=10)  # 1%

    result = check_quarantine_rate_threshold(rate, total_rows=1000)

    assert result["breached"] is False
    assert result["rate"] == pytest.approx(0.01)


def test_check_quarantine_rate_threshold_breached_above_threshold():
    rate = compute_quarantine_rate(passed_count=900, quarantined_count=100)  # 10%

    result = check_quarantine_rate_threshold(rate, total_rows=1000)

    assert result["breached"] is True
    assert result["rate"] == pytest.approx(0.1)


def test_check_quarantine_rate_threshold_skips_thin_batch_even_if_rate_high():
    # 5 of 20 rows quarantined = 25%, well above threshold, but total_rows is
    # under MIN_ROWS_FOR_CHECK so the reading isn't trustworthy yet.
    rate = compute_quarantine_rate(passed_count=15, quarantined_count=5)

    result = check_quarantine_rate_threshold(rate, total_rows=20)

    assert result["total_rows"] < MIN_ROWS_FOR_CHECK
    assert result["breached"] is False


def test_check_quarantine_rate_threshold_uses_default_threshold():
    rate = QUARANTINE_RATE_THRESHOLD + 0.01

    result = check_quarantine_rate_threshold(rate, total_rows=1000)

    assert result["threshold"] == QUARANTINE_RATE_THRESHOLD
    assert result["breached"] is True


def test_build_dq_alert_message_includes_key_figures():
    result = check_quarantine_rate_threshold(0.15, total_rows=1000)

    message = build_dq_alert_message(result, passed_count=850, quarantined_count=150)

    assert "silver-transformations" in message
    assert "15.00%" in message
    assert "850" in message
    assert "150" in message
    assert "transactions_quarantine" in message


def test_raise_if_quarantine_rate_breached_raises_with_alert_body():
    result = check_quarantine_rate_threshold(0.15, total_rows=1000)

    with pytest.raises(DataQualityAlertError) as exc_info:
        raise_if_quarantine_rate_breached(result, passed_count=850, quarantined_count=150)

    assert "quarantine rate exceeded threshold" in str(exc_info.value)
    assert "850" in str(exc_info.value)


def test_raise_if_quarantine_rate_breached_is_a_noop_when_not_breached():
    result = check_quarantine_rate_threshold(0.01, total_rows=1000)

    raise_if_quarantine_rate_breached(result, passed_count=990, quarantined_count=10)


def test_raise_if_quarantine_rate_breached_is_a_noop_on_thin_batch():
    # High rate, but too few rows to trust — should not raise.
    result = check_quarantine_rate_threshold(0.25, total_rows=20)

    raise_if_quarantine_rate_breached(result, passed_count=15, quarantined_count=5)
