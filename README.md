<p align="center">
  <img src="builder-ui/public/logo.png" alt="Polymo" width="220">
</p>

Polymo turns REST APIs into Spark DataFrames with a single declarative configuration file. The library builds on top of the DataSource V2 implementation for PySpark 4, while the companion builder UI helps you design, validate, and preview connectors without writing code.

## Highlights
- Visual builder keeps a form-based editor and live YAML in sync, with validation and previews.
- Configuration is plain YAML: describe the base URL, pagination, query parameters, and optional record selectors—no custom code required.
- Spark-native DataSource exposes `spark.read.format("polymo")`, so connectors slot into existing ETL jobs, notebooks, or scheduled (lakeflow) pipelines.
- Fast sampling pipeline shows both DataFrame output and raw API pages, making it easy to debug response shapes and headers.
- Jinja templating, environment variable lookups, and runtime Spark options let you parameterise connectors for different environments.

## Install

```bash
# Lightweight core package with only httpx, pydantic and jinja2 dependencies
pip install polymo
# Adds Spark, FastAPI/uvicorn and frontend assets for the builder UI
pip install "polymo[builder]"
```

Polymo requires PySpark 4.x. The CLI enforces this requirement before launching the builder or smoke test helpers.

## Quick Start

1. **Describe a stream** in YAML:

   ```yaml
   version: 0.1
   source:
     type: rest
     base_url: https://jsonplaceholder.typicode.com
   stream:
     path: /posts
     params:
       _limit: 20
     infer_schema: true
   ```

2. **Read the API with Spark**:

   ```python
   from pyspark.sql import SparkSession
   from polymo import ApiReader

   spark = SparkSession.builder.getOrCreate()
   spark.dataSource.register(ApiReader)

   df = (
       spark.read.format("polymo")
       .option("config_path", "./config.yml")
       .option("token", "<YOUR_BEARER_TOKEN>")
       .load()
   )

   df.show()
   ```

3. **Use the builder UI** to iterate faster:

   ```bash
   polymo builder --port 9000
   ```

   The browser app walks you through the same settings, validates the YAML against the Python backend, runs sample requests, and lets you save polished configs.

## Project Pieces
- `src/polymo/` – PySpark DataSource, config validation, and REST client.
- `polymo builder` – FastAPI backend with a React/Tailwind single-page app under `builder-ui/`.
- `examples/` – Ready-to-run connector samples used by the smoke test and the builder landing screen.

## Where to Next
Read the [API reference](docs/api.md), [CLI documentation](docs/cli.md), or [dive into the builder UI](docs/index.md).

Contributions and early feedback welcome!
