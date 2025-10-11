<p align="center">
  <img src="builder-ui/public/logo.png" alt="Polymo" width="220">
</p>

<p align="center">
    <em>Turn REST APIs into Spark DataFrames with just a YAML file
</em>
</p>

<p align="center">
  <a href="https://github.com/dan1elt0m/polymo/actions/workflows/test.yml"><img alt="test" src="https://github.com/dan1elt0m/polymo/actions/workflows/test.yml/badge.svg"></a>
  <a href="https://github.com/dan1elt0m/polymo/actions/workflows/gh-pages.yml"><img alt="Publish Docs" src="https://github.com/dan1elt0m/polymo/actions/workflows/gh-pages.yml/badge.svg"></a>
  <img alt="PyPI - Python Version" src="https://img.shields.io/pypi/pyversions/polymo">
  <img alt="PyPI - Status" src="https://img.shields.io/pypi/status/polymo">
  <img alt="License BSD 3" src="https://img.shields.io/badge/license-BSD--3--Clause-blue?style=flat-square">
</p>

# Welcome to Polymo

Polymo makes it super easy to ingest APIs with Pyspark. You only need to define a YAML file.

My vision is that API ingestion doesn't need heavy, third party tools or hard to maintain custom code.
The heck, you don't even need Pyspark skills.


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
query.show()

```

Does it perform? Polymo can read in batches (pages in parallel) and therefore is much faster than row based solutions like UDFs.

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

## Contributing
It's still early days, but Polymo already supports a lot of features!
Is there something missing? Raise an issue or contribute!

Contributions and early feedback welcome!
