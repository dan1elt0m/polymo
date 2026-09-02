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

> **Since 1.2:** the `builder` extra is gone. `pip install polymo` now
> includes everything (FastAPI, Uvicorn, PySpark, PyArrow, requests) — there
> is nothing extra to opt into. The `polymo builder` subcommand is also
> gone; the bare `polymo` command launches the Builder directly. See the
> [CLI reference](cli.md) for the current flags.

## What was removed

| 0.x symbol / interface | Status in 1.0 |
|---|---|
| `spark.read.format("polymo")` / `spark.readStream.format("polymo")` | Removed. There is no Spark data source named `polymo` any more. |
| `polymo.ApiReader` | Removed. |
| `polymo.PolymoConfig` (and `load_config` / `dump_config` / `.reader_config()` / `.dump_yaml()`) | Removed. Nothing in polymo reads or writes YAML any more. |
| YAML connector files (`config.yml`, `.option("config_path", ...)`, `.option("config_json", ...)`) | Removed as a runtime input. The Builder's saved `*.polymo.json` files are a different, unrelated format (see below). |
| `polymo smoke` CLI subcommand | Removed. (As of 1.2, `polymo builder` is gone too — see the note below.) |
| `/api/format` builder endpoint | Removed along with the YAML export it powered. |
| `.option("token", ...)`, `.option("stream_batch_size", ...)`, and the rest of the Spark reader options | Removed — there is no reader to pass options to. The generated script has its own top-level constants (`BASE_URL`, `PARAMS`, `HEADERS`, ...) that you edit directly instead. The incremental options (`incremental_state_path` / `incremental_start_value` / `incremental_state_key`) live on as `stream.incremental.*` config — see below. |

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
2. Launch the Builder: `polymo`.
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
- **Incremental options moved from reader options into the config.** The
  0.x `.option("incremental_state_path", ...)`,
  `.option("incremental_start_value", ...)` and
  `.option("incremental_state_key", ...)` reader options are back as
  `stream.incremental.state_path` / `start_value` / `state_key` (the
  Builder's **State file or URL**, **Initial cursor value** and **State key
  override** fields), with the same semantics: a local path or `file://`
  URL is a plain file, any other scheme (`s3://`, `gs://`, `abfss://`,
  `dbfs://`) goes through fsspec, the seed only applies while nothing is
  stored, and the state file keeps the 0.x `{"streams": {key: {...}}}`
  shape (an existing 0.x file is read as-is). Defaults are unchanged:
  `<stream>_state.json` and `<stream>@<base_url>`. They generate constants
  (`STATE_PATH`, `START_VALUE`, `STATE_KEY`) rather than being read at run
  time. Since 1.7; 1.0–1.6 only supported the fixed local file. See
  [Incremental sync](config.md#incremental-sync).
- **`incremental_memory_state` is gone.** The 0.x process-global cursor
  cache has no meaning in a generated script, which always goes through the
  state file.
- **The new cursor is the maximum, not the last-seen value.** 0.x stored
  whatever `cursor_field` value it saw last; the generated `_Reader.read()`
  stores the highest value (string comparison) it yielded, and the write is
  monotone, so a partition that finishes late can never lower the cursor.
  Zero-pad numeric cursors if you rely on ordering.
- **`pagination`-strategy partitioning parallelizes again.** Since 1.7 a
  `partition.strategy: pagination` connector with page/offset pagination, a
  `page_size` and at least one of `total_pages_path` /
  `total_pages_header` / `total_records_path` / `total_records_header`
  generates the 0.x planner: the driver probes the first page once, resolves
  the page count with the 0.x precedence, and Spark reads one
  `InputPartition` per page. `total_records_*` is honoured for planning
  only (never as a stop condition), exactly as before. Without the strategy
  or without hints the script stays a sequential loop. 1.0–1.6 always ran
  this strategy sequentially. See [Partitioning](config.md#partitioning).
