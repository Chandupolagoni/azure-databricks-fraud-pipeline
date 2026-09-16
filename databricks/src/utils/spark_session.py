"""Shared Spark session / configuration helpers used across notebooks and jobs."""

from pyspark.sql import SparkSession


def get_spark(app_name: str = "fraud-platform") -> SparkSession:
    """Return a SparkSession configured for Delta Lake with sensible shuffle defaults.

    On Databricks, `spark` is already provided by the runtime; this helper exists so
    the same transformation modules can also run locally/in tests against a plain
    Spark + delta-spark install.
    """
    builder = (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config(
            "spark.sql.catalog.spark_catalog",
            "org.apache.spark.sql.delta.catalog.DeltaCatalog",
        )
        .config("spark.sql.shuffle.partitions", "auto")
        .config("spark.databricks.delta.optimizeWrite.enabled", "true")
        .config("spark.databricks.delta.autoCompact.enabled", "true")
    )

    try:
        from delta import configure_spark_with_delta_pip

        return configure_spark_with_delta_pip(builder).getOrCreate()
    except ImportError:
        # Running inside Databricks, where Delta is already on the classpath.
        return builder.getOrCreate()


def adls_path(container: str, storage_account: str, path: str = "") -> str:
    """Build an abfss:// path for the given ADLS Gen2 container/path."""
    base = f"abfss://{container}@{storage_account}.dfs.core.windows.net"
    return f"{base}/{path}" if path else base
