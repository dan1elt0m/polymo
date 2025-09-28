# polymo

Python-first REST connector for the Spark 4.x Python Data Source API.

## Quick start

1. Define a config file:

   ```yaml
   version: 0.1
   source:
     type: rest
     base_url: https://api.github.com
     auth:
       type: bearer
       token: ${env:GH_TOKEN}
   stream:
     name: repos
     path: /users/{user}/repos
     params:
       user: octocat
       per_page: 100
     pagination:
        type: link_header
     schema:
        infer: true
   ```

2. Register the source and read data:

   ```python
   from pyspark.sql import SparkSession
   from polymo import ApiReader 

   spark = SparkSession.builder.getOrCreate()
   spark.dataSource.register(ApiReader)

   df = (
       spark.read.format("polymo")
       .option("config_path", "./github.yml")
       .option("stream", "repos")
       .load()
   )
   ```

`polymo` handles config parsing, REST pagination (link headers today), simple schema inference.

## Builder UI

Requires builder extra: `pip install 'polymo[builder]'`.
Want a friendlier way to craft configs? Launch the local builder:

```bash
polymo builder --port 9000
```

## Smoke test

Requires extra: `pip install 'polymo[smoke]'`.

```bash
polymo smoke --config examples/jsonplaceholder.yml --limit 3
```

It registers the `polymo.rest` source against a local Spark session, reads the sample JSONPlaceholder `posts` stream, prints the inferred schema, and shows the first few rows.

## Status

- Supports Spark 4.x Python Data Source API (batch columnar reads).
- Incremental cursors, partitioning, and advanced pagination strategies are on the roadmap.

Contributions and early feedback welcome!
