<p align="center">
  <img src="builder-ui/public/logo.png" alt="Polymo" width="220">
</p>

# Welcome to Polymo

Polymo is a helper for pyspark that turns everyday web APIs into tables you can analyse. Point it at an API, tell it what you want to grab, and Polymo does the heavy lifting of fetching the data and lining it up neatly.

<!-- Centered clickable screenshot -->
<p align="center">
  <a href="docs/ui.png">
    <img src="docs/ui.png" alt="Polymo Builder UI - connector preview screen" width="860">
  </a>
</p>

```python
from pyspark.sql import SparkSession
from polymo import ApiReader

spark = SparkSession.builder.getOrCreate()
spark.dataSource.register(ApiReader)

df = (
    spark.read.format("polymo")
    .option("config_path", "./config.yml")  # YAML you saved from the Builder
    .option("token", "YOUR_TOKEN")  # Only if the API needs one
    .load()
)

df.show()
```

Structured Streaming works out of the box aswell:

```python
stream_df = (
    spark.readStream.format("polymo")
    .option("config_path", "./config.yml")
    .option("stream_batch_size", 100)
    .option("stream_progress_path", "/tmp/polymo-progress.json")
    .load()
)

query = stream_df.writeStream.format("memory").outputMode("append").queryName("polymo")
query.start()
```

## Why people use Polymo
- **No custom code required.** Describe your API once in a short, friendly YAML file or through the point-and-click Builder.
- **See results before you commit.** Preview the real responses, record-by-record, so you can fix issues early.
- **Works with Spark-based tools.** When you are ready, Polymo serves the data to your analytics stack using the same interface Spark already understands.
- **Designed for teams.** Save reusable connectors, share them across projects.

## Before you start
- Install Polymo with `pip install polymo`. If you want the Builder UI, add the extras: `pip install "polymo[builder]"`.
- Make sure you have access to the API you care about (base URL, token if needed, and any sample request parameters).

## What’s inside this project
- `src/polymo/` keeps the logic that speaks to APIs and hands data to Spark.
- `polymo builder` is a small web app (FastAPI + React) that guides you through every step. No need to run npm, the app is bundled with pip and ready to go.
- `examples/` contains ready-made configs you can copy, tweak, and use for smoke tests.
- `tests/test_datasource.py::test_stream_reader_batches` exercises the streaming reader end to end; run it with `pytest -k stream_reader_batches` for a quick smoke test.
- `notebooks/polymo_vs_udf_benchmark.ipynb` compares two approaches: Polymo’s DataSource batch endpoint vs a per-row Spark UDF. With the default 50ms simulated latency Polymo finishes ~10× faster than the per-row UDF. Tweak `PAGE_DELAY`, `page_size`, or the dataset size to mirror your own API.

## Run the Builder in Docker
- Build the dev-friendly image and launch the Builder with hot reload:

```bash
docker compose up --build builder
```

- The service listens on port `8000`; open <http://localhost:8000> once Uvicorn reports it is running.
- The image already bundles PySpark and OpenJDK 21;
- Stop with `docker compose down` and restart quickly using the cached image via `docker compose up builder`.

Have fun building connectors!

## Where to Next
Read the docs [here](https://dan1elt0m.github.io/polymo/)

Contributions and early feedback welcome!
