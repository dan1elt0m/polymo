# Polymo 1.0: from runtime library to code generator

Date: 2026-08-28
Status: draft, awaiting Daniel's review

## Why

Polymo currently asks users to take a runtime dependency on a young,
single-author library (82 downloads/month). That is a hard sell for
production pipelines. The pivot: polymo becomes a **dev-time
assistant**. The builder helps you click together a REST connector,
preview it live, and export a **standalone Python script with zero
polymo imports**. Users own the script; polymo never ships to
production.

## Product shape

- One entry point: `polymo builder` (works via `uvx polymo builder`).
- The builder exports exactly one artifact: a **Lakeflow/Spark
  Declarative Pipelines source file** using the current idiom
  `from pyspark import pipelines as dp` with `@dp.table` (not the
  retired `import dlt`). No other flavors.
- Generated scripts import only `requests` and `pyspark.pipelines`.
  All configuration is inlined as plain Python literals. No YAML, no
  config object, no env-var reads.
- Secrets stay plain and visible: when auth is bearer, the script gets
  a `API_TOKEN = "..."` variable at the top with a comment
  recommending users abstract it away, e.g. a
  `dbutils.secrets.get(...)` or Azure Key Vault lookup. Polymo never
  writes a real token into the script; the placeholder is filled by
  the user (the builder uses the session-supplied token only for
  preview, as today).
- TLS: default is plain `requests` (certifi). The template includes a
  short *commented* block for corporate-proxy environments
  ("pip install truststore and uncomment") so the script gains no
  extra hard dependency.
- Version 1.0.0, breaking. Short migration note in the README for 0.x
  users.

## Generator

New module `src/polymo/codegen/`:

- `generator.py` — `generate(config) -> str`.
- `templates/` — Jinja templates composed of feature blocks
  (pagination style, auth, retries, record selection) around a `dp`
  skeleton. Output is **specialized**: only the blocks the config
  uses are emitted. Typical output: 80–250 readable lines,
  ruff-clean. The fetch core is pure Python (no Spark imports) so it
  can be exec'd standalone; the `@dp.table` wiring sits below it.
- Schema: when the builder has an inferred or user-defined schema, it
  is emitted as an explicit DDL string in the script
  (`SCHEMA = "kenteken STRING, ..."`); otherwise the script falls back
  to `createDataFrame` inference.

### v1.0 feature coverage: full parity, simpler representation

Every feature the current runtime supports is covered — they are
known to work; only their representation changes. Each chosen option
is emitted as the simplest code that implements it (KISS per option):

- Pagination `none`/`offset`/`page`/`cursor`/`link_header`: the
  matching loop, nothing else.
- Auth bearer/OAuth2: bearer is a header; OAuth2 becomes a small
  `get_token()` function specialized to the configured grant.
- Retries/backoff, record selector paths, param/header templating:
  inlined plain-Python equivalents.
- Incremental: state read/written as a small JSON file at a
  user-visible path (plain `open()`; works with Databricks Volumes).
- Partitioned reads: the generated table function parallelizes the
  configured windows across executors with the same fetch core.
- Streaming: the script inlines a short, config-specialized Spark
  `DataSource` subclass (pyspark API, still zero polymo imports) —
  the one case where a plain fetch loop cannot express the feature.

## Builder changes

- **Preview executes the generated code.** The template is structured
  so the fetch core (pure functions, no Spark) can be exec'd on its
  own; the builder execs it and islices a sample. What you preview is
  byte-for-byte the code you export. No second engine, no drift.
- UI: the YAML pane becomes a read-only generated-code pane with
  copy/download. The form side stays.
- API: `/api/format` (YAML round-trip) is removed; `/api/validate`
  and `/api/sample` operate on the JSON config dict; new
  `/api/generate` returns the script for a config.
- Save/load of work-in-progress connectors uses JSON.
- `PolymoConfig` (pydantic) survives as internal builder state only —
  it is not a user-facing concept.

## Deletions (final phase)

- `datasource.py` (Spark custom DataSource `ApiReader`).
- `rest_client.py` (the templates become the only fetch
  implementation).
- YAML as a public interface (`parse_config`/`dump_config` public
  API, YAML docs).
- `cli.py` shrinks to `polymo builder`.

## Testing

1. **Golden files**: config → exact generated script snapshots, per
   feature block.
2. **Execution tests**: exec the generated fetch core against a local
   mock HTTP server; assert records returned and the exact request
   sequence (pagination off-by-ones live here). The `@dp` wiring is
   excluded from execution (cannot run outside a pipeline) and gets
   compile/structure assertions instead.
3. **Hygiene**: generated output must pass `ast.parse` and
   `ruff check`.

## Phasing (each phase ships green)

1. `codegen/` + `dp` template + all three test layers, covering the
   full feature matrix. Nothing user-visible.
2. Builder: preview via generated code, generated-code pane, YAML
   surfaces removed.
3. Delete runtime, rewrite docs, release 1.0.0.
