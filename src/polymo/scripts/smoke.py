#!/usr/bin/env python3
"""Quick smoke test for the polymo REST data source."""

from __future__ import annotations

import argparse
from argparse import ArgumentParser, Namespace
from pathlib import Path

from pyspark.sql import SparkSession

from polymo import ApiReader


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="examples/jsonplaceholder.yml",
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
    return parser.parse_args()


def main(args: Namespace) -> None:
    config_path = Path(args.config).expanduser().resolve()
    if not config_path.exists():
        raise SystemExit(f"Config file not found: {config_path}")

    spark = SparkSession.builder.appName("polymo-smoke").getOrCreate()
    try:
        spark.dataSource.register(ApiReader)
        reader = spark.read.format(args.format).option("config_path", str(config_path))
        if args.stream:
            reader = reader.option("stream", args.stream)

        df = reader.load()
        df.printSchema()
        df.show(args.limit, truncate=False)
    finally:
        spark.stop()
