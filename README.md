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
   streams:
     - name: repos
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

Want a friendlier way to craft configs? Install the package, then launch the local builder:

```bash
polymo builder --port 9000
```

The web app (FastAPI + vanilla JS) mirrors an Airbyte-style workflow: toggle between a UI builder and raw YAML, validate (and timestamp) config changes when you act (e.g., save, sample, switch views), and preview sample records in both DataFrame and JSON views—without leaving the browser.

## Smoke test

Run the bundled helper script (requires Spark 4.x available on your machine):

```bash
polymo smoke --config examples/jsonplaceholder.yml --limit 3
```

It registers the `polymo.rest` source against a local Spark session, reads the sample JSONPlaceholder `posts` stream, prints the inferred schema, and shows the first few rows.

## Status

- Supports Spark 4.x Python Data Source API (batch columnar reads).
- MVP feature set: bearer auth, link header pagination, schema inference for flat JSON payloads.
- Incremental cursors and advanced pagination strategies are on the roadmap.

Contributions and early feedback welcome!
