# Configuration Guide

Polymo stores connector settings in a short YAML file. Think of it as a recipe that explains where to fetch data, which knobs to turn on the API, and how to treat the results. You can create the file by hand or export it from the Builder UI—both formats are identical.

## What a minimal config looks like

```yaml
version: 0.1
source:
  type: rest
  base_url: https://api.example.com
stream:
  path: /v1/items
  infer_schema: true
```

That is enough to call `https://api.example.com/v1/items` once and let Polymo guess the columns from the response.

## Anatomy of the file

| Section | Plain-language meaning |
|---------|------------------------|
| `version` | Format version. Use `0.1` for now. |
| `source`  | Where the API lives. |
| `stream`  | What to request and how to shape the results. |

Everything else is optional and only appears when you need it.

## Source block

```yaml
source:
  type: rest
  base_url: https://api.example.com
```

- `type` is always `rest` at the moment.
- `base_url` is the front part of every request. Leave off the trailing slash; Polymo tidies it for you.
- Authentication details (like tokens) are **never** written here. They are supplied later when you run the connector.

## Stream block

### Path

```yaml
stream:
  path: /v1/items
```

- Must start with a `/`.
- You can use placeholders like `/repos/{owner}/{repo}`. At runtime, passing `owner=dan1elt0m` fills in the braces.

### Query parameters

```yaml
params:
  limit: 100
  status: active
```

- Sent on every request.
- Values can reference runtime options with `{{ options.limit }}` or read environment variables with `${env:API_KEY}`. If the environment variable is missing, Polymo raises a clear error when you preview or run the job.

### Headers

```yaml
headers:
  Accept: application/json
  X-Correlation-ID: "polymo-sample"
```

- Optional. Handy for APIs that expect versioning or custom IDs.
- Supports the same templating and environment shortcuts as parameters.

### Authentication

Add an `auth` block under `source` when the API requires credentials:

```yaml
source:
  type: rest
  base_url: https://api.example.com
  auth:
    type: oauth2
    token_url: https://auth.example.com/oauth/token
    client_id: my-client-id
    scope:
      - read
      - write
```

Supported methods:

- **none** – default; no auth added to requests.
- **bearer** – each request carries an `Authorization: Bearer <token>` header. Supply the token at runtime with `.option("token", "...")`; the Builder keeps the token in memory only. Running on Databricks? To fetch secrets/scope
- use `.option("token_scope", "my-scope").option("token_key", "api-token")` instead and Polymo will fetch the secret from the Databricks scope on the driver.
- **api_key** – Polymo injects the API key as a query parameter. Set `authType` to `api_key`, choose the parameter name, and supply the value at runtime (the Builder uses `.option("<param>", "...")` behind the scenes).
- **oauth2** – Implements the client-credentials flow. Provide `token_url`, `client_id`, optional `scope`, `audience`, and `extra_params` (a JSON object merged into the token request). The client secret should be passed at runtime via the Spark option `.option("oauth_client_secret", "...")`; exported YAML references it as `{{ options.oauth_client_secret }}` so secrets remain out of the file. On Databricks you can supply secrets without copying them into the notebook by pointing Polymo at scopes: `.option("oauth_client_id_scope", "my-scope").option("oauth_client_id_key", "client-id")` and `.option("oauth_client_secret_scope", "my-scope").option("oauth_client_secret_key", "client-secret")` pull both values from Databricks Secrets before the request starts.

The Builder mirrors these options and stores secrets only for the current browser session. When you re-open a saved connector, re-enter the secret before previewing or exporting.

### Pagination

```yaml
pagination:
  type: offset
  page_size: 100
  limit_param: limit
  offset_param: offset
```

Pick one of the supported behaviours:
- `none` – only one page is requested.
- `offset` – Polymo increments an offset query parameter (default `offset`) by the configured `page_size` (defaulting to the number of records returned) until an empty page is received. Override the parameter name or starting point with `offset_param` and `start_offset`.
- `page` – Polymo increments a page counter (default `page`) on every request and enforces an optional `page_size` via `limit_param` (default `per_page`). Adjust the behaviour with `page_param` and `start_page`.
- `cursor` – Polymo reads the next cursor value from the response payload or headers and sends it back via `cursor_param` (defaults to `cursor`). Combine with `cursor_path` (a list or dotted path such as `meta.next_cursor`) or `cursor_header` to tell Polymo where to find the cursor. Alternatively provide `next_url_path` when the API returns a fully qualified "next" link.
- `link_header` – legacy support that follows `Link: <...>; rel="next"` headers until there are no more pages.

Every pagination strategy stops when the API returns an empty list of records. Override that default by setting `stop_on_empty_response: false`.

#### Partition-aware pagination

When you provide either `total_pages_path`/`total_pages_header` or `total_records_path`/`total_records_header`, Polymo can estimate how many requests are required in advance. The Spark DataSource will use that information to create one input partition per page (for `page` pagination) or per offset step (for `offset` pagination), allowing Spark to read pages in parallel. For example:

```yaml
pagination:
  type: page
  page_size: 100
  page_param: page
  limit_param: per_page
  total_pages_path: [meta, total_pages]
```

or

```yaml
pagination:
  type: offset
  page_size: 500
  offset_param: offset
  total_records_header: X-Total-Count
```

If the total count hints are missing, Polymo falls back to a single Spark partition.

### Partition block

Define a `partition` block under `stream` to split the workload explicitly:

```yaml
partition:
  strategy: endpoints
  endpoints:
    - posts:/posts
    - comments:/comments
    - users:/users
```

Supported strategies:

- **pagination** – mirrors the pagination hints in the YAML. Including total counts (as shown above) lets Spark plan one partition per page; without the hints Polymo still works, but Spark keeps the job single-partition.
- **param_range** – generates a partition per value. Supply either `values: 1,2,3` or range fields (`range_start`, `range_end`, `range_step`, and optional `range_kind: date`). `value_template` and `extra_template` let you shape request parameters.
- **endpoints** – fans out over multiple paths. Each item can be `/path` or `name:/path`; the name shows up as `endpoint_name` in previews and Spark rows.

The Builder writes this block for you, and it exports cleanly in the YAML download. You can declare it by hand too—see `examples/jsonplaceholder_endpoints.yml` for full sample.

#### Overriding via runtime options

Any `.option("partition_strategy", ...)` call overrides the YAML block. The auxiliary options (`partition_param`, `partition_values`, `partition_endpoints`, and so on) are unchanged.

### Incremental fields

```yaml
incremental:
  mode: updated_at
  cursor_param: since
  cursor_field: updated_at
```

When `cursor_param` and `cursor_field` are populated Polymo performs an incremental sync:

- On the first request Polymo seeds the query with the last cursor value it knows about. The value is read from a JSON state file that you point to with `.option("incremental_state_path", "./polymo-state.json")`.
- The path may be local or remote (for example `s3://team-bucket/polymo/state.json`). Remote URLs require installing `fsspec`; if the library is missing Polymo raises a helpful error before making any HTTP calls.
- If the state file does not exist yet, provide a fallback with `.option("incremental_start_value", "2024-01-01T00:00:00Z")`.
- After every successful run the JSON file is updated with the newest cursor value observed in the stream. By default the entry key is `<stream name>@<base URL>`, but you can override it via `.option("incremental_state_key", "orders-prod")` when you want to share a state file between connectors.
- The stored cursor is only used when the query parameter is not already supplied in the config (so custom templates or overrides still win).
- If you skip `incremental_state_path`, Polymo keeps the last cursor in memory for as long as the Spark driver stays alive. This is handy for notebooks or iterative development. Disable that behaviour with `.option("incremental_memory_state", "false")` when you want each run to start fresh.

The JSON file uses a straightforward structure:

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

You can keep one state file per connector or share it—Polymo creates directories as needed and overwrites the entry atomically.

The repository includes `examples/incremental-state.json` as a ready-to-copy template.

## Benchmarks

Curious how Polymo compares to hand-rolled solutions? Check out `notebooks/polymo_vs_udf_benchmark.ipynb`. It spins up a local FastAPI service with simulated latency and contrasts Polymo’s paginated reader with both a Python UDTF (fetching 200 rows at a time) and a per-row Spark UDF. With the default 100 ms delay and 5,000 records, Polymo finishes roughly 9× faster than the per-row UDF and still leads the UDTF path. Tune `PAGE_DELAY`, page size, and dataset length to match your API.

### Schema vs. infer_schema

```yaml
infer_schema: true
schema: null
```

- Leave `infer_schema` set to `true` to let Polymo look at sample data and pick reasonable column types.
- Set `infer_schema: false` and provide a `schema` if you prefer to define the columns yourself.
- The schema string uses the same style as Spark: `id INT, title STRING, updated_at TIMESTAMP`. If you copy a schema from the Builder or preview, it is already formatted correctly.

### Record selector (for nested responses)

```yaml
record_selector:
  field_path: [data, items]
  record_filter: "{{ record.status == 'open' }}"
  cast_to_schema_types: true
```

- `field_path` points to the part of the JSON payload that holds the list of records. In the example above, Polymo follows `data → items`.
- `record_filter` lets you keep or drop rows using a simple expression. The word `record` refers to the current item.
- `cast_to_schema_types` tells Polymo to convert values to the column types you set in `schema` (handy when you want timestamps or numbers instead of plain strings).

### Runtime options

You will not see this block in YAML, but it is worth mentioning: options passed at runtime are available inside templates. For example:

```python
spark.read.format("polymo")
  .option("config_path", "./github.yml")
  .option("owner", "dan1elt0m")
  .option("token", os.environ["GITHUB_TOKEN"])            # or .option("token_scope", "creds").option("token_key", "github") on Databricks
  .load()
```

Prefer keeping everything in memory? Replace `config_path` with `.option("config_json", json.dumps(config_dict))` when you already have the config as a Python dictionary. Only one of `config_path` or `config_json` can be supplied at a time.

Inside your config you can reference `{{ options.owner }}` or `{{ options.token }}`. Keep tokens out of the YAML—pass them through `.option("token", ...)` instead.

For OAuth2, supply the client secret the same way: `.option("oauth_client_secret", os.environ["CLIENT_SECRET"])`. The exported YAML references it as `{{ options.oauth_client_secret }}` so the value never touches disk. When you run on Databricks, swap the environment variable for secret scopes by adding `.option("oauth_client_id_scope", "creds")`, `.option("oauth_client_id_key", "client-id")`, `.option("oauth_client_secret_scope", "creds")`, and `.option("oauth_client_secret_key", "client-secret")`.

## Putting it all together

### Structured Streaming

Polymo can also act as a streaming source. Point `spark.readStream` at the same YAML file and supply any runtime options you would normally pass to `read`:

```python
spark.readStream.format("polymo") \
  .option("config_path", "./jsonplaceholder_endpoints.yml") \
  .option("oauth_client_secret", os.environ["CLIENT_SECRET"]) \
  .option("stream_batch_size", 100) \
  .option("stream_progress_path", "/tmp/polymo-progress.json") \
  .load()
```

- `stream_batch_size` controls how many records are fetched per micro-batch (defaults to 100).
- `stream_progress_path` stores a tiny JSON file with the last processed offset so the next query run resumes where it left off.
- Incremental options such as `incremental_state_path` still apply and are the recommended way to avoid re-processing old records.

All of the authentication rules above still apply—use `.option("token", ...)` for bearer tokens and `.option("oauth_client_secret", ...)` for OAuth2.

Here is a fuller example, annotated with comments:

```yaml
version: 0.1
source:
  type: rest
  base_url: https://api.github.com
stream:
  path: /repos/{owner}/{repo}/issues
  params:
    state: open
    per_page: 50
    labels: "{{ options.label | default('bug') }}"  # uses runtime option with a fallback
  headers:
    Accept: application/vnd.github+json
  pagination:
    type: page
    page_size: 50
    limit_param: per_page
  incremental:
    mode: updated_at
    cursor_param: since
    cursor_field: updated_at
  infer_schema: false
  schema: |
    number INT,
    title STRING,
    state STRING,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    user STRUCT<login: STRING>
  record_selector:
    field_path: [*]
    record_filter: "{{ record.pull_request is none }}"
    cast_to_schema_types: true
```

When you preview or run this connector, remember to pass `owner`, `repo`, and `token` as options. Templates fill them in, pagination walks through every issue, and the schema shapes the output into predictable columns.

If you ever feel unsure about a field, open the Builder UI—the form labels and tooltips mirror everything explained here.
