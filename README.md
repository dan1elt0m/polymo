<p align="center">
  <img src="builder-ui/public/logo.png" alt="Polymo" width="220">
</p>

# Welcome to Polymo

Polymo makes it super easy to ingest APIs with Pyspark. It's like slicing cake.

My vision is that API ingestion doesn't need heavy, third party tools or hard to maintain custom code.


<!-- Centered clickable screenshot -->
<p align="center">
  <a href="docs/ui.png">
    <img src="docs/ui.png" alt="Polymo Builder UI - connector preview screen" width="860">
  </a>
</p>

## How does it work?

Define a config file manually or use the recommended, lightweight builder UI. 
Once you are happy with your config, all you need to do is register the Polymo reader and tell Spark where to find the config:

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

Polymo is almost feature complete!

- Various Authentication options
- Many Pagination  patterns, plus automatic partition-aware reading when totals are exposed.
- Several partitioning stategies for parallel Spark reads.
- Incremental sync support with cursor parameters, JSON state files on local or remote storage, optional memory caching, and overrideable state keys.
- Schema controls that auto-infer types or accept Spark SQL schemas, along with record selectors, filtering expressions, and schema-based casting for nested responses.
- Structured Streaming compatibility with `spark.readStream`, tunable batch sizing, durable progress tracking, and a streaming smoke test mode.
- Error handling through configurable retry counts, status code lists, timeout handling, and exponential backoff settings.
- Jinja templating of query parameters gives you a ton of flexibility


## How to start?
Locally you probably want to install polymo with the UI: 

```bash
pip install "polymo[builder]"
```

This comes with UI deps such as pyspark

Running Polymo on an existing cluster in for instance databricks doesnt require these deps.
In that case, just install the bare minimum depa with
```bash
pip install polymo
```

## Launch the builder UI 

```bash 
polymo builder
```

#### (Optional) Run the Builder in Docker

```bash
docker compose up --build builder
```

- The service listens on port `8000`; open <http://localhost:8000> once Uvicorn reports it is running.

## Where to Next
Read the docs [here](https://dan1elt0m.github.io/polymo/)

Contributions and early feedback welcome!
