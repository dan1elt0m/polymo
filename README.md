<p align="center">
  <img src="builder-ui/public/logo.png" alt="Polymo" width="220">
</p>

<p align="center">
    <em>Turn any REST API into a standalone Lakeflow Declarative Pipelines connector — no runtime, just generated code.</em>
</p>

<p align="center">
  <a href="https://github.com/dan1elt0m/polymo/actions/workflows/test.yml"><img alt="test" src="https://github.com/dan1elt0m/polymo/actions/workflows/test.yml/badge.svg"></a>
  <a href="https://github.com/dan1elt0m/polymo/actions/workflows/gh-pages.yml"><img alt="docs" src="https://github.com/dan1elt0m/polymo/actions/workflows/gh-pages.yml/badge.svg"></a>
  <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/polymo">
</p>

# Welcome to Polymo

Polymo is a dev-time tool. You describe a REST API in the [Builder UI](docs/builder-ui.md), preview real responses, and export a standalone [Lakeflow Declarative Pipelines](https://docs.databricks.com/aws/en/dlt/) connector. The output is plain, typed Python that only needs `requests`, the standard library, and `pyspark` — nothing is imported from `polymo`, and there is no config file to load at runtime. The generated code is yours: edit it, version it, review it like any other code.

## What the builder generates

Pointing the builder at `https://jsonplaceholder.typicode.com/posts` produces a single file. Elided here, the real script also contains the retry/backoff and response-normalization helpers, and there are no comments to strip:

```python
"""Lakeflow Declarative Pipelines connector for posts."""

import time
from typing import Any, Iterator

import requests

BASE_URL: str = "https://jsonplaceholder.typicode.com"
PATH: str = "/posts"
PARAMS: dict[str, Any] = {"_limit": 20}
HEADERS: dict[str, str] = {}
TIMEOUT: float = 30.0


def fetch_records() -> list[dict[str, Any]]:
    ...


from pyspark import pipelines as dp
from pyspark.sql import SparkSession
from pyspark.sql.datasource import DataSource, DataSourceReader


class RestSource(DataSource):
    ...


spark = SparkSession.getActiveSession()
spark.dataSource.register(RestSource)


@dp.table(name="posts")
def posts():
    return spark.read.format("posts_source").load()
```

Every field you fill in — pagination, incremental sync, partitioning, filter pushdown, error handling, headers, query parameters, an explicit schema, XML responses, streaming tables — is baked in as a constant or a small block of specialized code. Options you don't use produce no code at all.

<p align="center">
  <a href="docs/ui.png">
    <img src="docs/ui.png" alt="Polymo Builder UI - connector preview screen" width="860">
  </a>
</p>

## How does it work?

Open the Builder, describe your API (base URL and path are the only required fields), and press **Preview** to see the DataFrame, the raw records, and the raw API responses side by side. The config panel and the preview share a resizable split; collapse the panel or use focus mode when you want the whole width for the data. When you're happy, switch to the **Generated Code** tab and download the script.

Ready to run it on Databricks? The **Deploy** tab walks through it in order — Profile → Target → Bootstrap → Deploy → Run:

1. Pick a Databricks CLI profile, then a catalog and schema (or type a schema name).
2. **Bootstrap** writes a complete [Databricks Asset Bundle](https://docs.databricks.com/dev-tools/bundles/) project: the connector as an installable package under `src/`, the pipeline under `pipelines/`, and a `databricks.yml` that builds the wheel and attaches it to a serverless pipeline.
3. **Deploy** and **Run** drive `databricks bundle deploy` and `databricks bundle run` without leaving the Builder, with the CLI output docked below.

Secrets never land in generated code. Each auth field (bearer token, API key, OAuth2 client secret) and any `{{ options.<name> }}` placeholder can reference a Databricks secret scope or a Unity Catalog service credential backed by Azure Key Vault; the pipeline resolves the value on the driver and passes it to the reader, and the Builder redacts it from every preview. Requires the [Databricks CLI](https://docs.databricks.com/dev-tools/cli/) and a `~/.databrickscfg` profile — see [Deploy to Databricks](docs/builder-ui.md#deploy-to-databricks) for the full walkthrough.

See the [Connector options reference](docs/config.md) for what every Builder field generates, and the [Builder UI walkthrough](docs/builder-ui.md) for a guided tour.

## How to start?

```bash
pip install polymo
```

This installs everything you need, Builder UI included — FastAPI, Uvicorn, PySpark, PyArrow, and requests all come along.

`polymo` is never a dependency of the scripts it generates.

## Launch the builder UI

```bash
polymo
```

Or without installing it first:

```bash
uvx polymo
```

#### (Optional) Run the Builder in Docker

```bash
docker compose up --build builder
```

The service listens on port `8000`; open <http://localhost:8000> once Uvicorn reports it is running.

## Migrating from polymo 0.x?

The YAML runtime (`spark.read.format("polymo")`, `PolymoConfig`, `polymo smoke`) is gone since 1.0. See [docs/migration-1.0.md](docs/migration-1.0.md) for what changed, and pin `polymo<1.0` (0.11.0 is the last release with the old runtime) if you're not ready to move yet.

## Where to Next

Read the docs [here](https://dan1elt0m.github.io/polymo/).

Other material:
- Step by step example: [medium blogpost](https://medium.com/@d.e.tom89/turn-any-rest-api-into-spark-dataframes-in-minutes-with-polymo-028a48113eb1) (written for the 0.x YAML runtime — see the [migration guide](docs/migration-1.0.md) for what changed)

## Contributing

Is there something missing? Raise an issue or contribute! Contributions and early feedback welcome.

---
If Polymo helped, a ⭐ makes my day
