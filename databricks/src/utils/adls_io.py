"""Read/write helpers for the medallion ADLS Gen2 zones."""

from dataclasses import dataclass

from pyspark.sql import DataFrame, SparkSession


@dataclass(frozen=True)
class MedallionPaths:
    storage_account: str
    raw_container: str = "raw"
    curated_container: str = "curated"
    checkpoints_container: str = "checkpoints"

    def raw(self, source_system: str) -> str:
        return f"abfss://{self.raw_container}@{self.storage_account}.dfs.core.windows.net/{source_system}"

    def silver(self, table: str) -> str:
        return f"abfss://{self.curated_container}@{self.storage_account}.dfs.core.windows.net/silver/{table}"

    def gold(self, table: str) -> str:
        return f"abfss://{self.curated_container}@{self.storage_account}.dfs.core.windows.net/gold/{table}"

    def checkpoint(self, stream_name: str) -> str:
        return f"abfss://{self.checkpoints_container}@{self.storage_account}.dfs.core.windows.net/{stream_name}"


def read_raw_csv(spark: SparkSession, paths: MedallionPaths, source_system: str) -> DataFrame:
    return (
        spark.read.option("header", True)
        .option("inferSchema", False)
        .csv(paths.raw(source_system))
    )


def write_delta(df: DataFrame, path: str, mode: str = "append", partition_by: list[str] | None = None) -> None:
    writer = df.write.format("delta").mode(mode)
    if partition_by:
        writer = writer.partitionBy(*partition_by)
    writer.save(path)


def upsert_delta(df: DataFrame, path: str, merge_keys: list[str], spark: SparkSession) -> None:
    """Merge (upsert) new records into an existing Delta table by business key."""
    from delta.tables import DeltaTable

    if not DeltaTable.isDeltaTable(spark, path):
        write_delta(df, path, mode="overwrite")
        return

    target = DeltaTable.forPath(spark, path)
    merge_condition = " AND ".join(f"target.{k} = source.{k}" for k in merge_keys)

    (
        target.alias("target")
        .merge(df.alias("source"), merge_condition)
        .whenMatchedUpdateAll()
        .whenNotMatchedInsertAll()
        .execute()
    )
