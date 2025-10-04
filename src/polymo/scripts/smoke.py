#!/usr/bin/env python3
"""Quick smoke test for the polymo REST data source."""

from __future__ import annotations

import argparse
from argparse import Namespace
import shutil
import tempfile
from pathlib import Path
from pyspark.sql import SparkSession

from polymo import ApiReader


def _default_config_path() -> Path:
    try:
        from importlib import resources

        examples = resources.files("polymo.builder.static.examples")
        resource = examples.joinpath("jsonplaceholder.yml")
        with resources.as_file(resource) as path:
            if path.exists():
                target = (
                    Path(tempfile.gettempdir()) / "polymo-jsonplaceholder-smoke.yml"
                )
                shutil.copy2(path, target)
                return target
    except Exception:
        pass

    return Path("examples/jsonplaceholder.yml").expanduser()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default=str(_default_config_path()),
        help="Path to the YAML config file (default: %(default)s)",
    )
    parser.add_argument(
        "--stream",
        default=None,
        help="Optional stream name to load (default: first stream in config)",
    )
    parser.add_argument(
        "--format",
        default="polymo",
        help="Registered DataSource name to use (default: %(default)s)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Number of rows to show from the resulting DataFrame",
    )
    parser.add_argument(
        "--streaming",
        action="store_true",
        help="Run a streaming smoke test instead of a batch read",
    )
    parser.add_argument(
        "--stream-batch-size",
        type=int,
        default=100,
        help="Rows to fetch per streaming micro-batch (default: %(default)s)",
    )
    return parser.parse_args()


def main(args: Namespace) -> None:
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    spark = SparkSession.builder.appName("polymo-smoke").getOrCreate()
    try:
        spark.dataSource.register(ApiReader)
        if getattr(args, "streaming", False):
            _run_streaming_smoke(spark, args, config_path)
        else:
            _run_batch_smoke(spark, args, config_path)
    finally:
        spark.stop()


def _run_batch_smoke(spark: SparkSession, args: Namespace, config_path: Path) -> None:
    reader = spark.read.format(args.format).option("config_path", str(config_path))
    if args.stream:
        reader = reader.option("stream", args.stream)

    df = reader.load()
    df.printSchema()
    df.show(args.limit, truncate=False)


def _run_streaming_smoke(
    spark: SparkSession, args: Namespace, config_path: Path
) -> None:
    table_name = "polymo_smoke_stream"
    spark.catalog.dropTempView(table_name) if spark.catalog.tableExists(
        table_name
    ) else None

    progress_dir = Path(tempfile.mkdtemp(prefix="polymo-smoke-"))
    progress_path = progress_dir / "progress.json"

    reader = (
        spark.readStream.format(args.format)
        .option("config_path", str(config_path))
        .option("stream_batch_size", getattr(args, "stream_batch_size", 100))
        .option("stream_progress_path", str(progress_path))
    )
    if args.stream:
        reader = reader.option("stream", args.stream)

    stream_df = reader.load()

    query = (
        stream_df.writeStream.format("memory")
        .outputMode("append")
        .queryName(table_name)
        .trigger(once=True)
        .start()
    )
    query.awaitTermination()

    df = spark.sql(f"SELECT * FROM {table_name}")
    df.printSchema()
    df.show(args.limit, truncate=False)

    query.stop()
