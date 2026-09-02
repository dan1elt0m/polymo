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
  lookup, e.g. `dbutils.secrets.get(...)`) before running the script. Maps
  to `source.auth.type = "bearer"`.
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

### Databricks secret-scope references

Instead of leaving the generated `API_TOKEN` / `API_KEY` / `CLIENT_SECRET`
constant as `"REPLACE_ME"`, any auth secret slot can carry a reference to a
Databricks secret scope: add a `secret` object alongside the other auth
fields —

```yaml
source:
  auth:
    type: bearer
    secret:
      scope: my-scope
      key: my-key
```

(the same shape works for `api_key` and `oauth2`'s `client_secret` slot).
Both `scope` and `key` are required and must be non-empty — this is a
**reference only**; the config, the generated script, and the builder's
logs never contain the secret value itself. Codegen resolves it at runtime
via a generated `_dbx_secret(scope, key)` helper instead:

```python
API_TOKEN: str = _dbx_secret("my-scope", "my-key")
```

`_dbx_secret` is emitted once per script, only when at least one slot
references a secret. It resolves the value on the driver via
`DBUtils(SparkSession.getActiveSession()).secrets.get(scope, key)`, and
raises a clear `RuntimeError` if called outside a Databricks cluster (no
active Spark session) — swap the call for the literal value if you need to
run the script somewhere else.

The same reference shape works for `{{ options.<name> }}` placeholders (see
[Query parameters & headers](#query-parameters-headers) below): set
`stream.option_secrets.<name>` to `{"scope": ..., "key": ...}` and the
resulting `OPT_<NAME>` constant resolves via `_dbx_secret` too. An
`option_secrets` entry for a name that isn't actually referenced anywhere is
harmless — it's simply unused, not a config error.

```yaml
stream:
  headers:
    Authorization: "Basic {{ options.api_key_b64 }}"
  option_secrets:
    api_key_b64:
      scope: my-scope
      key: api-key-b64
```

The builder preview cannot resolve real Databricks secrets outside a
Databricks cluster: previewing a secret-ref config without a session token
sends the same `"REPLACE_ME"` dummy the unresolved-placeholder path already
does, so the request still fires (and fails/succeeds against the real API
exactly as an unresolved placeholder would); supplying a session token in
the preview UI overrides the relevant auth slot (bearer/api_key/oauth2)
with that token, the same way it does for a plain placeholder. `OPT_*`
secret refs have no override in preview and always get the dummy.

**Setting a `secret` reference in the Builder** happens through the
**Secret source** toggle on each auth field (Bearer/API Key/OAuth2 Client
Secret) — switch it from "enter for preview / placeholder in export" to
"Databricks secret scope" and pick a scope + key from the dropdowns (backed
by `databricks secrets list-scopes`/`list-secrets` for the profile chosen on
the [Deploy tab](builder-ui.md#deploy-to-databricks)). See
[Deploy to Databricks → Secrets](builder-ui.md#secrets) for the UI walkthrough.

**At deploy time**, this reference resolves differently in a bundle project
than in the exported script above. `src/<pkg>/client.py` — the file the
[Deploy tab](builder-ui.md#deploy-to-databricks) bootstraps under a
project's `src/` directory — ships as an installed wheel, so Spark
reconstructs its `DataSource` on every executor with a fresh
`import <pkg>.client` and no Spark session available; a module-level
`_dbx_secret(...)` call there would fail on every read. So a secret-ref slot
in `client.py` is instead typed `API_TOKEN: str | None = None` (the
`_dbx_secret` helper function itself is still generated, just not called at
module scope), and `pipelines/<stream>.py` — which only ever runs on the
driver — calls it there and threads the resolved value through as a
DataSource reader option (`secret_api_token`, etc.). Spark reconstructs the
reader fresh on every executor (it pickles the driver's reader object by
reference and re-imports `client.py` there, wiping any module state the
driver had set), so `src/<pkg>/source.py` installs the resolved option onto
`client`'s globals twice: once on the driver when the reader is built
(covering schema inference), and again on the worker at the top of every
`read()`/`readBetweenOffsets()` call, immediately before that call's fetch.
If a slot is still `None` once a fetch path actually needs it, the generated
code raises a clear `RuntimeError` naming the slot instead of silently
sending `None` to the real API. Nothing about deploying the bundle itself
(`databricks bundle deploy`) touches secret values — deploy only uploads
source files and cluster/pipeline definitions; the secret is resolved only
once the pipeline actually runs (`databricks bundle run`).

### UC service-credential secret references

An alternative to a Databricks secret scope: resolve the secret through a
[Unity Catalog service credential](https://docs.databricks.com/en/connect/unity-catalog/index.html)
and an Azure Key Vault secret instead. The same four auth secret slots
(`bearer`'s token, `api_key`'s value, `oauth2`'s `client_secret`) can carry a
`uc_secret` object in place of `secret` —

```yaml
source:
  auth:
    type: bearer
    uc_secret:
      credential: my-service-credential
      vault_url: https://my-vault.vault.azure.net/
      secret_name: my-key
```

`credential`, `vault_url`, and `secret_name` are all required and must be
non-empty — again, a **reference only**; the value itself never appears in
the config. `secret` and `uc_secret` are **mutually exclusive** on the same
auth slot — setting both raises a config error. Codegen resolves it at
runtime via a generated `_uc_secret(credential, vault_url, secret_name)`
helper instead:

```python
API_TOKEN: str = _uc_secret("my-service-credential", "https://my-vault.vault.azure.net/", "my-key")
```

`_uc_secret` is emitted once per script, only when the auth slot references
a UC secret. It calls
`dbutils.credentials.getServiceCredentialsProvider(credential)` to get an
Azure-SDK-compatible credential, then uses it to authenticate an Azure Key
Vault `SecretClient(vault_url=..., credential=...)` and fetch
`secret_name`. It raises a clear `RuntimeError` if called outside a
Databricks cluster (no active Spark session), if `dbutils`/the Key Vault SDK
aren't available, or if the resolved secret has no value — the error
message names the required `azure-keyvault-secrets` package. Unlike
`_dbx_secret`, there is no `{{ options.* }}` placeholder equivalent —
`option_secrets` stays scope-only (see above); use `auth.uc_secret` for the
primary auth secret slot.

**Setting a `uc_secret` reference in the Builder** happens through the same
**Secret source** toggle described above — pick **UC credential (Key
Vault)** and fill in the credential, vault URL, and secret name. See
[Deploy to Databricks → Secrets](builder-ui.md#secrets) for the UI
walkthrough.

**At deploy time**, this reference resolves the same way a Databricks
secret-scope reference does (see above): `src/<pkg>/client.py` keeps the
slot typed `str | None = None`, and `pipelines/<stream>.py` calls
`_uc_secret` driver-side and threads the resolved value through as a
DataSource reader option, resolved only once the pipeline actually runs
(never at `databricks bundle deploy` time). The generated `pyproject.toml`
adds `azure-keyvault-secrets` as a dependency automatically whenever a
`uc_secret` reference is present, so the built wheel (see [Deploy to
Databricks → Project bootstrap](builder-ui.md#project-bootstrap)) carries
what `_uc_secret` needs.

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

## Filter pushdown

The **Filter pushdown** panel (`stream.pushdown_params`) maps DataFrame
column names to API query parameter names:

```json
"pushdown_params": {"status": "status", "owner_id": "owner"}
```

With a mapping in place, the generated `_Reader` implements Spark's
`pushFilters()` (Python Data Source filter pushdown, Spark 4.1+): an
**equality filter on a mapped column** is taken out of Spark's post-read
filtering and sent to the API as that query parameter on every request the
read makes — the sequential fetch, every static window, and the page probe
and per-page fetches of the `pagination` strategy alike.

```python
spark.read.format("posts_source").load().filter(col("status") == "active")
# -> GET /posts?status=active
```

What is pushed and what is not:

- Pushed: `EqualTo` on a top-level column listed in `pushdown_params`, with
  a non-null value (rendered with `str()`, so `owner_id == 42` becomes
  `?owner=42`).
- Left to Spark (returned from `pushFilters` unchanged): every other filter
  shape — `In`, comparisons, `Not`, `IsNull`, string matches — plus
  equality on an unmapped column, on a nested column (`a.b`), or against
  `null`. Those still apply; they just run after the read.

Precedence: a pushed value **overrides** an explicit `stream.params` entry
of the same name (you asked for the filter, so it wins). Mapping a column
to a parameter the fetch loop assigns itself (`page`/`offset`/`limit`, the
pagination or incremental `cursor_param`, a `param_range` partition param)
or to a query-placed `api_key` name is a config error, as is mapping two
columns to one parameter.

Runtime note: Spark only calls `pushFilters` when
`spark.sql.python.filterPushdown.enabled` is on (it defaults to off in
Spark 4.1/4.2, and a reader that implements `pushFilters` is rejected while
it is off). The standalone script sets that conf on the session itself,
next to the `dataSource.register(...)` call; a bundle never sets Spark conf
from source code — its `databricks.yml` declares it under the pipeline
resource instead (`configuration: {spark.sql.python.filterPushdown.enabled:
"true"}`), so it arrives as pipeline configuration. Filter pushdown is batch-only; a
streaming table with `pushdown_params` is rejected at generation time. When
the mapping is empty the generated script contains no pushdown code at all.

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
the same sequential fetch loop. Together with `total_records_path` /
`total_records_header` they also drive the `pagination` partition strategy,
which plans one Spark partition per page from them — see
[Partitioning](#partitioning) below.

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
partition strategy, `_Reader` reads everything in a single partition; when
it does (see [Partitioning](#partitioning) below), `_Reader.partitions()`
returns one `InputPartition` per window or page and `read()` fetches only
that partition's records — Spark runs each partition on whichever executor
it schedules it to, in parallel.

## Partitioning

Set a **Partition strategy** (`stream.partition.strategy`) to change how
the generated `@dp.table` function fetches data:

- **none** (default) — plain sequential fetch, as above.
- **pagination** — one partition per page, planned at read time. The
  driver (`_Reader.partitions()`) fetches the first page once through a
  generated `_probe_total_pages()`, resolves the page count from the
  pagination hints, and returns one `InputPartition` per page; each
  partition's `read()` then fetches exactly that page via `fetch_page()`
  (`page = start_page + i` for page pagination, `offset = start_offset +
  i * page_size` for offset pagination). Requires page or offset
  pagination with a `page_size` and at least one hint — otherwise the
  generated script is the plain sequential loop and contains no probe code
  at all. Hint precedence is the 0.x one: `total_pages_path`, then
  `total_pages_header`, then `total_records_path`, then
  `total_records_header` (records become `ceil(total / page_size)`
  pages). A hint that resolves to nothing, or to 0 or 1 pages, falls back
  to a single partition that reads the whole stream sequentially.
- **param_range** — generates one static request "window" per value at
  generation time; the inline Data Source (see
  [above](#how-the-batch-table-reads)) turns each into its own
  `InputPartition`, so windows are fetched in parallel across executors.
  Supply either explicit `values` (comma-separated) or a range
  (`range_start`, `range_end`, `range_step`, and `range_kind: date` for date
  ranges). `value_template` / `extra_template` shape how each value is
  injected into request parameters.
- **endpoints** — one window per path. Each entry is `/path` or
  `name:/path`. Also parallelized, one partition per endpoint. Windows
  carry only the `path`; **generated records are flat, with no
  `endpoint_name` field or `data` wrapper** — see [Endpoints partitioning
  changed](migration-1.0.md#behavioral-differences-to-check-for) if you're
  migrating a 0.x `endpoints` connector.

Partition strategies are batch-only; a streaming table with any strategy
other than `none` is rejected at generation time.

## Incremental sync

Fill in **Cursor param** and **Cursor field** (`stream.incremental.cursor_param`
/ `cursor_field`) to make the generated script track a cursor between runs;
**Mode** is a free-text label stored alongside the cursor. The remaining
options mirror the 0.x reader options of the same name, now as config:

| Option (`stream.incremental.*`) | Generated constant | Default | Meaning |
|---|---|---|---|
| `cursor_param` | `CURSOR_PARAM` | — | Query parameter the stored cursor is sent as. Applied with `setdefault`, so an explicit `stream.params` entry (or a partition window's `extra_params`) with the same name wins. |
| `cursor_field` | `CURSOR_FIELD` | — | Response field whose highest value becomes the next cursor. Dotted paths (`meta.updated_at`) walk nested objects. |
| `mode` | — | `null` | Free-text label written into the state entry (`updated_at`, `created_at`, ...). |
| `state_path` | `STATE_PATH` | `<stream>_state.json` next to the script | Where the cursor lives. A plain path or `file://` URL is a local file — `/Volumes/main/raw/state/orders.json` on Databricks (FUSE) is the usual choice, since every executor must reach it. Any other URL scheme (`s3://`, `gs://`, `abfss://`, `dbfs://`) goes through [fsspec](https://filesystem-spec.readthedocs.io/); install the matching backend (`s3fs`, `gcsfs`, `adlfs`) on the cluster. |
| `start_value` | `START_VALUE` | `None` | Seed sent as the cursor while nothing is stored yet. Ignored once the state file has a value. |
| `state_key` | `STATE_KEY` | `<stream>@<base_url>` | Entry key inside the state file, so several connectors can share one file. |

The state file is a JSON document with one entry per key, merged into on
every write (other keys are preserved):

```json
{
  "streams": {
    "issues@https://api.github.com": {
      "cursor_param": "since",
      "cursor_field": "updated_at",
      "cursor_value": "2024-03-22T18:15:00Z",
      "mode": "updated_at",
      "updated_at": "2024-03-22T18:16:05Z"
    }
  }
}
```

Reading is lenient — a 0.x state file is picked up as-is: the entry may sit
under `streams` or at the top level, may be a dict with `cursor_value` (or
the older `value`) or a bare scalar; a missing file or unparseable JSON
simply means "no cursor yet" (and `start_value` applies).

How the generated code uses it:

- `fetch_records()` (and `fetch_page()` for the `pagination` strategy)
  reads the cursor once up front — the stored value, else `START_VALUE` —
  and sends it as `CURSOR_PARAM` on every page of the run.
- The inline Data Source's `read()` tracks the **maximum** `cursor_field`
  value it yields (compared as strings — ISO timestamps sort correctly;
  zero-pad numeric cursors) and commits it once the partition is done.
  This is the one deliberate difference from the 0.x runtime, which kept
  the *last-seen* value.
- The commit is monotone: `_write_state()` re-reads the stored value and
  only writes when the new cursor is higher. With `param_range`,
  `endpoints` or `pagination` partitioning, `read()` runs once per
  partition on whichever executor owns it, so partitions may commit in any
  order — the file still ends at the global maximum, and a partition that
  saw nothing newer never regresses it. A local `state_path` therefore has
  to be one every executor can reach (a Volume path), or use a remote URL.
- For the `pagination` strategy the driver resolves the cursor once in
  `partitions()` and hands the same value to the probe and to every page
  partition, so all pages of a run are fetched against the cursor the page
  count was planned with.

The Builder's **Preview** never touches your state: it generates the same
`fetch_records()` against a throwaway state path, so it always shows a
first run (seeded from `start_value` if set) and never writes a file.

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

Supported scalar types: `string` / `varchar` / `char` / `text`, `boolean` /
`bool`, `double` / `float64`, `float` / `real`, `tinyint`, `smallint`, `int`
/ `integer`, `bigint` / `long`, `timestamp`, `date`, `variant`, and
`decimal(precision, scale)` (or bare `decimal` / `numeric` for
`decimal(38, 18)`).

**Nested types are supported**: `ARRAY<T>`, `MAP<K, V>`, and
`STRUCT<name: T, ...>` (a struct field's `name: T` colon is optional —
`name T` works too, matching Spark's own DDL grammar), any of which can
nest inside each other to any depth, e.g.:

```
id INT, tags ARRAY<STRING>, meta MAP<STRING, STRING>,
address STRUCT<street: STRING, zip: STRING>,
history ARRAY<STRUCT<at: TIMESTAMP, note: STRING>>
```

Field names — top-level or inside a `STRUCT<...>` — can be backtick-quoted
(`` `first name` STRING ``) when they contain characters a bare identifier
can't (spaces, commas, etc.).

The validator (`_validate_ddl_syntax`/`_validate_type_expr` in `config.py`)
checks this grammar without needing pyspark installed, so it runs during
`generate()` even from a bare `pip install polymo`. It's a syntax check
only — it doesn't guarantee Spark itself will accept the string, though in
practice every DDL string this validator accepts is valid input to
`StructType.fromDDL`, since it deliberately mirrors that grammar.

With an **explicit** schema, dict/list values from the API pass straight
through to Spark as-is for `STRUCT`/`ARRAY`/`MAP` columns — the column
needs the real structure, not a stringified copy of it. With an
**inferred** schema, nested values are still JSON-encoded into a `STRING`
column by the generated `_cell()` helper, because schema inference never
produces a nested type (it only ever infers `BOOLEAN`/`BIGINT`/`DOUBLE`/
`STRING`), so a raw dict/list value would otherwise crash the read.

Any other mismatch between a declared column's type and the actual value
the API returns (e.g. a field you typed as `INT` that sometimes comes back
as text, or a `STRUCT` whose declared fields don't match the dict's keys)
is not handled — Spark raises when it can't fit the value into the column,
same as it always has. Fix it in your schema, not by relying on the
generated code to coerce it for you.

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

The one exception is a [Databricks secret-scope
reference](#databricks-secret-scope-references) or a [UC service-credential
reference](#uc-service-credential-secret-references): the *call site* —
`_dbx_secret("scope", "key")` or `_uc_secret("credential", "vault_url",
"secret_name")` — is still baked in as a literal at generation time, but the
secret *value* it resolves is looked up fresh on the driver every time the
generated script runs.

If you're coming from the 0.x YAML runtime, see the
[migration guide](migration-1.0.md) for the full list of what moved or
disappeared, plus a checklist for rebuilding an old connector in the
Builder.
