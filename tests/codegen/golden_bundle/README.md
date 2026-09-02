# jsonplaceholder-demo

Databricks Asset Bundle for the `posts` stream.

- `databricks.yml` — bundle, `whl` artifact, pipeline resource (`main.raw`)
- `pyproject.toml` — packages `src/jsonplaceholder_demo` as the wheel (built via `uv build --wheel`)
- `src/jsonplaceholder_demo/client.py` — fetch/schema code
- `src/jsonplaceholder_demo/source.py` — the DataSource + reader, built on `jsonplaceholder_demo.client`
- `pipelines/posts.py` — imports the DataSource from `jsonplaceholder_demo.source`, wires the `@dp.table`

## Deploy

Requires [`uv`](https://docs.astral.sh/uv/) on the deploy machine (builds the wheel).

    databricks bundle deploy -t dev
    databricks bundle run -t dev jsonplaceholder_demo_pipeline

Table lands at `main.raw.posts`. Use `-t prod` for production.
Runs `serverless: true`; a classic cluster needs the wheel as a cluster library instead.
