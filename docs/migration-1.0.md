# Migrating from polymo 0.x

Polymo 1.0 removes the runtime connector entirely. Polymo is now a **dev-time
code generator only**: the [Builder UI](builder-ui.md) turns a form into a
standalone Python script, and nothing in that script imports `polymo`. If you
are not ready to move yet, pin the last 0.x release and keep using the
runtime as-is:

```bash
pip install "polymo<1.0"   # or pip install polymo==0.11.0
```

0.11.0 is the final 0.x release. It keeps the YAML runtime, `PolymoConfig`,
and `polymo smoke` working exactly as documented in its own docs snapshot.
Nothing in 0.11.0 is deprecated-but-functional in 1.0 — it is gone.

## What was removed

| 0.x symbol / interface | Status in 1.0 |
|---|---|
| `spark.read.format("polymo")` / `spark.readStream.format("polymo")` | Removed. There is no Spark data source named `polymo` any more. |
| `polymo.ApiReader` | Removed. |
| `polymo.PolymoConfig` (and `load_config` / `dump_config` / `.reader_config()` / `.dump_yaml()`) | Removed. Nothing in polymo reads or writes YAML any more. |
| YAML connector files (`config.yml`, `.option("config_path", ...)`, `.option("config_json", ...)`) | Removed as a runtime input. The Builder's saved `*.polymo.json` files are a different, unrelated format (see below). |
| `polymo smoke` CLI subcommand | Removed. `polymo builder` is the only subcommand. |
| `/api/format` builder endpoint | Removed along with the YAML export it powered. |
| `.option("token", ...)`, `.option("incremental_state_path", ...)`, `.option("stream_batch_size", ...)`, and the rest of the Spark reader options | Removed — there is no reader to pass options to. The generated script has its own top-level constants (`BASE_URL`, `PARAMS`, `HEADERS`, ...) that you edit directly instead. |

What's unchanged: the *ideas* behind pagination, auth, incremental sync,
partitioning, and record selection all carry forward — they are just
expressed as Builder form fields that generate code instead of YAML that a
runtime interprets. See the [Connector options reference](config.md) for the
current shape of each.

## Rebuilding an old YAML connector

There is deliberately no YAML importer. The Builder's `*.polymo.json` save
format is a different, work-in-progress JSON shape (it exists to let you
pause and resume a form-in-progress, not to import legacy configs), so the
fastest path is to re-enter your settings by hand:

1. Open your old `config.yml` (or however you saved the connector) next to
   the Builder.
2. Launch the Builder: `polymo builder`.
3. Walk each section of the form and copy the equivalent value across —
   `source.base_url` → **Base URL**, `stream.path` → **Stream Path**,
   `stream.pagination` → the **Pagination** section, `stream.auth` → the
   **Authentication** section, and so on. The
   [Connector options reference](config.md) maps every old YAML key to its
   Builder field and to what it now generates.
4. Click **Preview** to confirm the connector still fetches the data you
   expect, then export the script from the **Generated Code** tab.
5. Optionally save the in-progress form as a `*.polymo.json` file so you can
   reopen and tweak it later — this is unrelated to your old YAML file and
   is not portable back to the 0.x runtime.

Most connectors take a few minutes to rebuild this way since the field names
map almost one-to-one.

## Behavioral differences to check for

A few things generated scripts do differently from the 0.x runtime, even
when the underlying settings look the same:

- **Endpoints partitioning drops the wrapper.** In 0.x, the `endpoints`
  partition strategy tagged every row with an `endpoint_name` field and
  nested the payload under `data`. Generated scripts emit **flat records**
  with no wrapper — each row is exactly what your record selector picked out
  of that endpoint's response, with nothing indicating which endpoint it
  came from. If your downstream code filtered or grouped by `endpoint_name`,
  add that column yourself (e.g. give each endpoint its own generated
  script, or add a partition-index column) before relying on it.
- **Incremental state now lives in a fixed local file.** 0.x let you point
  `incremental_state_path` at any local or remote path (including
  `s3://...`). The generated script always reads/writes a local
  `<stream-name>_state.json` next to itself — there's no equivalent of
  `incremental_state_path`, `incremental_start_value`, or
  `incremental_state_key` in the generated code. The Builder's Incremental
  section still has fields with those names, but they only affect the
  **Preview** panel's own test run — edit the generated script directly if
  you need a different state location (e.g. a Databricks Volume path; the
  generated comment shows an example).
- **`pagination`-strategy partitioning no longer parallelizes.** In 0.x, a
  `partition.strategy: pagination` block combined with `total_pages_path` /
  `total_records_path` hints let the Spark data source plan one partition
  per page and fan reads out across executors. Generated scripts run
  pagination-strategy connectors as a single sequential loop — only
  `param_range` and `endpoints` partitioning produce a parallel fan-out in
  the generated code now: the inline `DataSource` every batch `@dp.table`
  reads through (see [How the batch table
  reads](config.md#how-the-batch-table-reads)) turns each window into its
  own `InputPartition`. The `total_pages_*` hints still work as a
  pagination stop condition; `total_records_*` is accepted by the config
  shape for compatibility but has no effect on generated code.
