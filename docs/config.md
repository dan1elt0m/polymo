# Connector Options Reference

Polymo has no config file and no runtime. You describe a connector once in
the [Builder UI](builder-ui.md), and every field you fill in changes what
the exported Python script looks like. This page documents each option, the
JSON key it maps to (the same shape `generate()` and `parse_config()` accept
in Python, and what the Builder's saved `*.polymo.json` files use
internally), and what it generates.

You will only write this JSON by hand if you are calling `polymo.generate()`
directly instead of using the form — see the [API reference](api.md). Most
people never touch it.

## Shape of a connector

A connector is one `RestSourceConfig`: a base URL, optional auth, and a
single stream (path + how to page through it, select records, and shape the
schema). In JSON form:

```json
{
  "version": "0.1",
  "source": {
    "type": "rest",
    "base_url": "https://api.example.com"
  },
  "stream": {
    "path": "/v1/items",
    "infer_schema": true
  }
}
```

That is enough for `generate()` to produce a script that fetches
`https://api.example.com/v1/items` once and infers columns from the
response — the same as filling in just **Base URL** and **Stream Path** in
the Builder and leaving everything else at its default.

## Base configuration

- **Base URL** (`source.base_url`) — the root of every request. The
  generated script stores it as the `BASE_URL` constant. Leave off the
  trailing slash.
- **Table name** (`stream.name`) — becomes the dp table name
  (`@dp.table(name=...)`), sanitized to a SQL identifier at export time.
  Optional: leave it blank and the Builder derives one from the stream path
  instead (e.g. `/v1/items` → `v1_items`).
- **Stream Path** (`stream.path`) — appended to `BASE_URL` and stored as
  `PATH`. Must start with `/`. You can use placeholders like
  `/repos/{owner}/{repo}`; the Builder's reader options are wired to fill
  these in — see [Reader options](#reader-options) below.
- **Streaming table** (`stream.streaming`) — every generated `@dp.table`
  ingests through a small Spark `DataSource` registered inline in the
  script — Lakeflow Declarative Pipelines requires a Spark data source
  either way, so batch tables get one too (see
  [How the batch table reads](#how-the-batch-table-reads) below). Turning
  this on switches which kind: the inline source becomes a
  `SimpleDataSourceStreamReader` and the table reads via
  `spark.readStream.format(...)` instead of `spark.read.format(...)`.
  Requires an explicit schema and `offset` or `page` pagination; not
  compatible with incremental sync or a partition strategy.
- **Response format** (`stream.response_format`, `stream.xml_record_path`)
  — see [XML responses](#xml-responses) below.

## Authentication

Set an **Auth Type** in the Builder's Authentication section. It is not
persisted in a saved config — you re-enter secrets each time you reopen a
connector.

- **None** (default) — no auth added to requests.
- **Bearer Token** — the generated script gets an `API_TOKEN = "REPLACE_ME"`
  constant near the top; edit it in place (or swap it for a secret-store
  lookup — the generated comment shows a Databricks example) before
  running the script. Maps to `source.auth.type = "bearer"`.
- **API Key** — a first-class auth type. Choose a **Placement** (Header or
  Query parameter) and a **Name** (e.g. `X-API-Key` for a header, or
  `api_key` for a query parameter). Maps to
  `source.auth = {"type": "api_key", "in": "header" | "query", "name": "<name>"}`.
  The key *value* is never stored in the config, same as Bearer — the
  generated script gets an `API_KEY = "REPLACE_ME"` constant near the top
  (edit it in place, or swap it for a secret-store lookup, same as the
  Bearer/OAuth2 placeholders); at request time it is applied as
  `session.headers["<name>"] = API_KEY` (header placement) or
  `params["<name>"] = API_KEY` (query placement).
- **OAuth 2.0 (Client Credentials)** — maps to
  `source.auth = {"type": "oauth2", "token_url": ..., "client_id": ..., "scope": [...], "audience": ..., "extra_params": {...}}`.
  The generated script gets a `CLIENT_SECRET = "REPLACE_ME"` constant and a
  `get_token()` helper that performs the client-credentials POST before
  every request. `scope` is space-joined free text in the form; `extra_params`
  is a JSON object merged into the token request body.

## Query parameters & headers

- **Params** (`stream.params`) → the `PARAMS` constant in the generated
  script, sent on every request.
- **Headers** (`stream.headers`) → the `HEADERS` constant.
- Values may reference `{{ options.<name> }}` (see
  [Reader options](#reader-options)). If `<name>` was supplied as a Spark
  reader option at generation time, it is resolved once into a literal value
  baked into the script — no templating left at runtime. If it was not
  supplied (the common case for an exported script, since `/api/generate`
  passes no options), the reference instead becomes an `OPT_<NAME>`
  placeholder constant near the top of the script (defaulting to
  `"REPLACE_ME"`), interpolated into `PARAMS`/`HEADERS`/`PATH` wherever it
  was referenced — edit that constant after export, or wire it up to a
  secret store the same way as the Bearer/OAuth2 placeholders.

## Reader options

The **Spark reader options** panel supplies values used to resolve path
placeholders (`{user_id}` in `/users/{user_id}/posts`) and any
`{{ options.* }}` references in params/headers/auth fields, all at
generation time. Fill in `owner=dan1elt0m` here and the generated script's
`PATH`/`PARAMS` constants already have `dan1elt0m` baked in — there is
nothing left to pass at runtime.

## Pagination

Pick a strategy in the **Pagination & incremental settings** panel
(`stream.pagination.type`):

- `none` — one page only.
- `offset` — increments an offset parameter (`offset_param`, default
  `offset`) by `page_size` on each request until an empty page comes back.
  `start_offset` sets the initial value.
- `page` — increments a page counter (`page_param`, default `page`),
  optionally capping page size via `limit_param` (default `per_page`).
  `start_page` sets the initial value.
- `cursor` — reads the next cursor from the response body
  (`cursor_path`, a dotted path such as `meta.next_cursor`) or a response
  header (`cursor_header`), and sends it back via `cursor_param` (default
  `cursor`). `next_url_path` is an alternative for APIs that return a fully
  qualified "next" link instead of a bare cursor value.
- `link_header` — follows `Link: <...>; rel="next"` response headers.

Every strategy stops once the API returns an empty page. This is not
configurable: the generated script's fetch loop always breaks on an empty
page. `stop_on_empty_response` is accepted for config compatibility but has
no effect on generated code.

`total_pages_path` / `total_pages_header` (under **Partition-aware
pagination hints**) let the generated script know when to stop without
waiting for an empty page — it's an extra stop condition, evaluated inside
the same sequential fetch loop.

!!! note "No more Spark-side partition planning"
    In the old runtime, these hints (plus `total_records_path` /
    `total_records_header`) let the Spark data source estimate the page
    count up front and fan reads out across executors — one partition per
    page. Codegen has no such planner: a `pagination`-strategy connector
    always runs as a single sequential loop in the generated script.
    `total_pages_*` still trims the loop early; `total_records_*` is
    accepted for config compatibility but has no effect on generated code.
    If you need real parallelism, use `param_range` or `endpoints`
    partitioning instead (below) — those *do* generate a parallel
    fan-out, one `InputPartition` per window.

## How the batch table reads

Every generated `@dp.table` — batch or streaming — ingests through a Spark
`DataSource` registered inline in the script, because Lakeflow Declarative
Pipelines requires a Spark data source rather than a bare Python value; a
batch table can no longer just build a `DataFrame` in Python and return it.
Concretely, the script defines a `RestSource(DataSource)` (its `schema()`
returns the DDL, its `reader()` builds a `_Reader`) and a
`_Reader(DataSourceReader)` whose `read()` calls `fetch_records()` and
yields one tuple per record; the table body is just
`spark.read.format("<name>_source").load()`. When the connector has no
windows, `_Reader` reads everything in a single partition; when it does
(`param_range` / `endpoints`, see [Partitioning](#partitioning) below),
`_Reader.partitions()` returns one `InputPartition` per window and `read()`
fetches only that window's records — Spark runs each partition on whichever
executor it schedules it to, in parallel.

## Partitioning

Set a **Partition strategy** (`stream.partition.strategy`) to change how
the generated `@dp.table` function fetches data:

- **none** (default) — plain sequential fetch, as above.
- **pagination** — same sequential fetch; this strategy exists for
  compatibility but does not change codegen (see the note above).
- **param_range** — generates one static request "window" per value at
  generation time; the inline Data Source (see
  [above](#how-the-batch-table-reads)) turns each into its own
  `InputPartition`, so windows are fetched in parallel across executors.
  Supply either explicit `values` (comma-separated) or a range
  (`range_start`, `range_end`, `range_step`, and `range_kind: date` for date
  ranges). `value_template` / `extra_template` shape how each value is
  injected into request parameters.
- **endpoints** — one window per path. Each entry is `/path` or
  `name:/path`. Also parallelized, one partition per endpoint.

Only `param_range` and `endpoints` produce this parallel fan-out, because
only they can be fully expanded into a literal list of windows at generation
time — see [Endpoints partitioning changed](migration-1.0.md#behavioral-differences-to-check-for)
if you're migrating a 0.x `endpoints` connector: **generated records are
flat, with no `endpoint_name` field or `data` wrapper.**

## Incremental sync

Fill in **Mode**, **Cursor param**, and **Cursor field**
(`stream.incremental.mode` / `cursor_param` / `cursor_field`) to make the
generated script track a cursor between runs:

- Before each request, the script reads the last cursor value from a local
  `<stream-name>_state.json` file next to itself (created automatically) and
  sends it via `cursor_param`.
- After the run, the newest value of `cursor_field` seen across the fetched
  records is written back to that file — from inside the inline Data
  Source's `read()` (see [How the batch table
  reads](#how-the-batch-table-reads) above), which tracks the max locally
  as it yields records and writes it once done.
- For `param_range` / `endpoints` connectors, `read()` runs once per
  partition/window, so each partition tracks and writes its own max
  independently; with more than one partition, whichever partition finishes
  last wins. Batch tables re-fetch everything on every run regardless of
  the cursor, so a stale write only costs some redundant fetching next
  time, not missed data. `STATE_PATH` must point somewhere every
  partition's executor can reach (e.g. a Databricks Volume — see the note
  below) for state to be read back correctly on the next run.

The Incremental panel also has **State path**, **Start value**, **State
key**, and **Keep in memory** fields. These only affect what the **Preview**
panel does when test-fetching incrementally — they are not part of the
generated script, which always uses the fixed `<stream-name>_state.json`
path described above. Edit the generated `STATE_PATH` constant by hand if
you need it to point elsewhere (the generated comment shows a Databricks
Volume path as an example).

## Error handling & retries

The **Error handling** panel (`stream.error_handler`) controls the
generated script's retry loop:

- `max_retries` — attempts before giving up (default 5).
- `retry_statuses` — HTTP statuses to retry, e.g. `5XX`, `429`.
- `retry_on_timeout` / `retry_on_connection_errors` — retry on
  `requests` timeout/connection exceptions too.
- `backoff.initial_delay_seconds`, `backoff.max_delay_seconds`,
  `backoff.multiplier` — exponential backoff between attempts.

Leave the panel untouched to keep the defaults.

## Record selector

For APIs that nest the record list inside the response body, the **Record
selector** panel (`stream.record_selector`) configures how the generated
`_records()` function digs it out:

- `field_path` — a list of keys/`*` wildcards, e.g. `["data", "items"]`
  walks `payload["data"]["items"]`.
- `record_filter` — a boolean Python expression evaluated per record, e.g.
  `record.get('status') == 'open'`.
- `cast_to_schema_types` — coerce values to match your declared `schema`
  (below) instead of leaving them as raw JSON types.

This section is JSON-only; it has no effect on XML responses (see below).

## Schema

Toggle **Infer schema** (`stream.infer_schema`) to skip pinning a DDL. The
inline Data Source's `schema()` (see [How the batch table
reads](#how-the-batch-table-reads) above) then calls a generated
`_infer_schema()` helper, which samples up to 50 records from
`fetch_records()` (split evenly across windows for a `param_range` /
`endpoints` connector, so a column that only appears in one window's
records is still picked up) and derives a DDL string from their Python
types — widening a column that mixes ints and floats to `DOUBLE`, and
falling back to `STRING` for any other type conflict or for `null`/dict/list
values. This is good for getting started, but it costs an extra request
every time the table runs, and the shape can shift if the API's response
shape changes. **An explicit schema is recommended** for anything beyond
initial exploration.

Turn it off and fill in **Schema** (`stream.schema`) to pin an explicit
Spark SQL DDL string, comma-separated `name TYPE` pairs:

```
id INT, title STRING, price DECIMAL(10,2), created_at TIMESTAMP
```

Supported types: `string` / `varchar` / `char` / `text`, `boolean` / `bool`,
`double` / `float64`, `float` / `real`, `tinyint`, `smallint`, `int` /
`integer`, `bigint` / `long`, `timestamp`, `date`, `variant`, and
`decimal(precision, scale)` (or bare `decimal` / `numeric` for
`decimal(38, 18)`).

**Nested types are not supported.** `STRUCT<...>`, `ARRAY<...>`, `MAP<...>`,
and backtick-quoted field names are all rejected by validation — every
field must be a flat, scalar column. If an API response has a nested
object you want as a typed column today, either flatten it with a
`record_filter`/custom post-processing after fetching, leave `infer_schema`
on, or edit the generated script's `SCHEMA` constant by hand after export
(the generator's DDL validator only runs at generation time, not on a
script you've already exported and modified).

Rather than reject a dict/list value it finds in a record at read time, the
generated `_cell()` helper JSON-encodes it into a string, so it lands in a
`STRING` column instead of crashing the read. Any other mismatch between a
declared column's type and the actual value the API returns (e.g. a field
you typed as `INT` that sometimes comes back as text) is not handled —
Spark raises when it can't fit the value into the column, same as it always
has. Fix it in your schema, not by relying on the generated code to coerce
it for you.

## XML responses

Set **Response format** to `XML` and fill in an **XML record path**
(`stream.xml_record_path`) — an `ElementTree.findall()`-style path selecting
each record element, e.g. `.//contact` or `contacts/contact`. The generated
script parses the response with `xml.etree.ElementTree` and, for each
matched element, builds a record dict from its attributes (prefixed `@`) and
its direct children (`{child.tag: child.text}`).

Keep these gotchas in mind:

- **Nested containers flatten to empty/whitespace text, not a value.**
  `child.text` only captures the text immediately inside `<child>` before
  its first sub-element — if `<child>` itself has children, `child.text` is
  usually `None` or pure whitespace, not the nested content. There is no
  automatic nested-XML flattening. If the data you need is one level deeper
  than a record, point `xml_record_path` at that deeper element instead of
  trying to pull it out through the parent.
- **Duplicate sibling tags: last one wins.** Each child becomes a plain dict
  key, so `<item><tag>a</tag><tag>b</tag></item>` produces `{"tag": "b"}` —
  `"a"` is silently overwritten. Rename or restructure the XML upstream if
  you need every occurrence.
- **Namespaced documents need Clark notation.** For
  `<ns:contact xmlns:ns="...">`, `xml_record_path` must use
  `{http://the/actual/namespace/uri}contact`, not the `ns:contact` prefix
  form — `ElementTree.findall()` doesn't resolve XML namespace prefixes on
  its own.
- XML responses are incompatible with `cursor_path`, `next_url_path`,
  `total_pages_path`, `total_records_path`, and the record selector's
  `field_path` — all of those dig through a decoded JSON payload, which
  doesn't exist for an XML response. Generation fails with a clear error if
  you combine them.

## Runtime options in generated scripts

There are none. Every option above is resolved once, at generation time,
into literal constants in the exported script (`BASE_URL`, `PATH`, `PARAMS`,
`HEADERS`, `SCHEMA`, ...). Editing the connector after export means editing
the script directly, or changing the Builder form and re-exporting.

If you're coming from the 0.x YAML runtime, see the
[migration guide](migration-1.0.md) for the full list of what moved or
disappeared, plus a checklist for rebuilding an old connector in the
Builder.
