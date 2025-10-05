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

## Why people use Polymo
- **No custom code required.** Describe your API once in a short, friendly YAML file or through the point-and-click Builder.
- **See results before you commit.** Preview the real responses, record-by-record, so you can fix issues early.
- **Works with Spark-based tools.** When you are ready, Polymo serves the data to your analytics stack using the same interface Spark already understands.
- **Designed for teams.** Save reusable connectors, share them across projects, and keep secrets (like tokens) out of files.
- **Speedy and efficient.** Polymo handles batch requests and pagination automatically, so you get your data faster than with per-row UDFs.

## Pick your path
- **Mostly clicking?** Open the [Builder UI](docs/builder-ui.md) and follow the guided screens. It is the easiest way to create a connector from scratch.
- **Prefer a checklist?** Read the [Configuration guide](docs/config.md) for a plain-language tour of every field in the YAML file.

## Before you start
- Install Polymo with `pip install polymo`. If you want the Builder UI, add the extras: `pip install "polymo[builder]"`.
- Make sure you have access to the API you care about (base URL, token if needed, and any sample request parameters).
- Check that PySpark version 4 or newer is available. Polymo uses Spark under the hood to keep data consistent.

## Supported features
- Declarative REST connectors defined in YAML or through the Builder, with path placeholders, runtime option templates, and environment variable helpers.
- Browser-based Builder UI with autosave, preview modes (table, records, raw API), schema copy, and a synced YAML editor.
- Lightweight CLI including `polymo builder` for launching the UI and `polymo smoke` for batch or streaming validation runs.
- Authentication helpers covering no auth, bearer tokens, API keys injected as parameters, and OAuth2 client-credentials exchanges with scoped requests.
- Pagination engines for single-shot, offset, page, cursor, next-link, and HTTP `Link` header patterns, plus partition-aware hints when totals are exposed.
- Workload partitioning via pagination hints, explicit endpoint fan-out, or parameter ranges (numeric and date) for parallel Spark reads.
- Incremental sync support with cursor parameters, JSON state files on local or remote storage, optional memory caching, and overrideable state keys.
- Schema controls that auto-infer types or accept Spark SQL schemas, along with record selectors, filtering expressions, and schema-based casting for nested responses.
- Structured Streaming compatibility with `spark.readStream`, tunable batch sizing, durable progress tracking, and a streaming smoke test mode.
- Resilient error handling through configurable retry counts, status code lists, timeout handling, and exponential backoff settings.

## Quick tour

1. **Launch the Builder (optional but recommended).** Run `polymo builder --port 9000` and open the provided link in your browser.
2. **Describe your API.** Fill in a base URL like `https://jsonplaceholder.typicode.com`, pick the endpoint `/posts`, and add filters such as `_limit: 20` if you only need a sample.
3. **Preview the data.** Press the Preview button to see a table of records, the raw API replies, and any error messages.
4. **Save the connector.** Download the YAML config or write it directly to your project folder. Tokens stay out of the file and are passed in later.
5. **Use it in Spark.** Load the file with the short code snippet below or copy/paste from the Builder’s tips panel.

The Builder keeps a local library of every connector you work on. Use the header’s connector picker to hop between drafts, open the library to rename or export them, and never worry about losing your place. The header even shows the installed Polymo version for quick support checks.


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

### Streaming too

Structured Streaming works out of the box:

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

Use the same runtime options as `read` (tokens, OAuth2 client secrets, incremental state paths, etc.). `stream_batch_size` caps the number of rows per micro-batch and `stream_progress_path` stores a tiny JSON file so restarts resume from the same offset.

Want a quick check without writing code? Run `polymo smoke --streaming` and the CLI will execute a one-off micro-batch using the bundled JSONPlaceholder example (or a YAML you pass in).

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
