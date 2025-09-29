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

### Pagination

```yaml
pagination:
  type: link_header
```

Pick one of two behaviours:
- `none` – only one page is requested.
- `link_header` – Polymo follows `Link: <...>; rel="next"` headers until there are no more pages.

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
  .option("token", os.environ["GITHUB_TOKEN"])
  .load()
```

Inside your config you can reference `{{ options.owner }}` or `{{ options.token }}`. Keep tokens out of the YAML—pass them through `.option("token", ...)` instead.

## Putting it all together

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
    type: link_header
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
