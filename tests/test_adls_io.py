import sys
from pathlib import Path

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1] / "databricks" / "src"))

pyspark = pytest.importorskip("pyspark")

from utils.adls_io import MedallionPaths  # noqa: E402
from utils.spark_session import adls_path  # noqa: E402


@pytest.fixture
def paths():
    return MedallionPaths(storage_account="fraudplatformdev")


def test_raw_path_uses_raw_container_and_source_system(paths):
    assert (
        paths.raw("card_network")
        == "abfss://raw@fraudplatformdev.dfs.core.windows.net/card_network"
    )


def test_silver_path_uses_curated_container_with_silver_prefix(paths):
    assert (
        paths.silver("transactions")
        == "abfss://curated@fraudplatformdev.dfs.core.windows.net/silver/transactions"
    )


def test_gold_path_uses_curated_container_with_gold_prefix(paths):
    assert (
        paths.gold("fraud_daily_summary")
        == "abfss://curated@fraudplatformdev.dfs.core.windows.net/gold/fraud_daily_summary"
    )


def test_silver_and_gold_share_the_curated_container_but_never_collide(paths):
    table = "account_profile"
    silver_path = paths.silver(table)
    gold_path = paths.gold(table)

    assert silver_path != gold_path
    assert "/silver/" in silver_path
    assert "/gold/" in gold_path


def test_checkpoint_path_uses_dedicated_checkpoints_container(paths):
    assert (
        paths.checkpoint("card_auth_ingestion")
        == "abfss://checkpoints@fraudplatformdev.dfs.core.windows.net/card_auth_ingestion"
    )


def test_container_names_are_overridable():
    custom = MedallionPaths(
        storage_account="fraudplatformprod",
        raw_container="raw-prod",
        curated_container="curated-prod",
        checkpoints_container="checkpoints-prod",
    )

    assert custom.raw("card_network").startswith(
        "abfss://raw-prod@fraudplatformprod.dfs.core.windows.net/"
    )
    assert custom.silver("transactions").startswith(
        "abfss://curated-prod@fraudplatformprod.dfs.core.windows.net/"
    )
    assert custom.checkpoint("stream").startswith(
        "abfss://checkpoints-prod@fraudplatformprod.dfs.core.windows.net/"
    )


def test_medallion_paths_is_frozen():
    paths = MedallionPaths(storage_account="fraudplatformdev")

    with pytest.raises(AttributeError):
        paths.storage_account = "someone-elses-account"


def test_adls_path_without_subpath_returns_bare_container_uri():
    assert (
        adls_path("raw", "fraudplatformdev")
        == "abfss://raw@fraudplatformdev.dfs.core.windows.net"
    )


def test_adls_path_with_subpath_appends_it():
    assert (
        adls_path("curated", "fraudplatformdev", "silver/transactions")
        == "abfss://curated@fraudplatformdev.dfs.core.windows.net/silver/transactions"
    )


def test_adls_path_matches_medallion_paths_raw_for_equivalent_inputs():
    storage_account = "fraudplatformdev"
    medallion = MedallionPaths(storage_account=storage_account)

    assert adls_path("raw", storage_account, "card_network") == medallion.raw(
        "card_network"
    )
