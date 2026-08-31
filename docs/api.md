# Python API Reference

Most people never call polymo from Python — the [Builder UI](builder-ui.md)
covers the whole workflow (describe, preview, export). The five names below
are the entire public surface of the `polymo` package; they exist mainly for
the Builder itself (`src/polymo/builder/app.py` calls `parse_config` and
`generate` behind `/api/validate`, `/api/sample`, and `/api/generate`), and
for scripting connector generation outside the UI — e.g. generating a batch
of connectors from a list of API definitions in CI.

```python
from polymo import CodegenError, RestSourceConfig, config_to_dict, generate, parse_config
```

## `parse_config(raw, token=None, options=None) -> RestSourceConfig`

Validates a plain dict describing a connector and returns a
`RestSourceConfig`. The dict shape is the same one the
[Connector options reference](config.md#shape-of-a-connector) documents —
`{"version": "0.1", "source": {...}, "stream": {...}}` — and is what the
Builder's saved `*.polymo.json` files and its `/api/*` request bodies carry
around internally. Raises `polymo.config.ConfigError` (a `ValueError`
subclass) on anything invalid, including an unsupported schema DDL string.

```python
from polymo import parse_config

config = parse_config({
    "version": "0.1",
    "source": {"type": "rest", "base_url": "https://jsonplaceholder.typicode.com"},
    "stream": {"path": "/posts", "params": {"_limit": 20}, "infer_schema": True},
})
```

- `token` — a bearer token to attach when `source.auth.type == "bearer"`.
  Kept out of the returned config's serialized form; only used to populate
  `RestSourceConfig.auth.token` in memory.
- `options` — a dict of reader-option values used to resolve
  `{{ options.<name> }}` references and `{placeholder}` path segments at
  generation time (see
  [Reader options](config.md#reader-options)).

`parse_config` does not require `pyspark` to be installed — schema DDL is
validated with a small pyspark-free grammar checker, not by constructing
real Spark types. That keeps `pip install polymo` (without the `builder`
extra) enough to call `parse_config`/`generate`.

## `generate(config: RestSourceConfig) -> str`

Renders a `RestSourceConfig` into the full standalone Python source of a
Lakeflow Declarative Pipelines script — the exact same string the Builder's
**Generated Code** tab and download button show. Raises `CodegenError` if
the config can't be expressed as a script — for example, `streaming=True`
without a compatible schema/pagination combination, or an XML
`response_format` combined with a JSON-path feature.

```python
from polymo import generate

script = generate(config)
with open("posts.py", "w") as f:
    f.write(script)
```

The returned script has no `polymo` import in it. It only needs `requests`,
the standard library, and `pyspark` (for the `@dp.table` wiring) to run.

## `config_to_dict(config: RestSourceConfig) -> dict`

The inverse direction: turns a `RestSourceConfig` back into the canonical
plain-dict shape, with secrets stripped (a bearer/oauth2 auth block keeps
only its `type` and non-secret fields, never the token or client secret).
Used by the Builder to round-trip a config it just validated back into JSON
for the frontend, and by anything that wants to inspect or persist a config
without holding onto the secret values.

## `RestSourceConfig` / `CodegenError`

`RestSourceConfig` (from `polymo.config`) is the frozen dataclass everything
above passes around — `version`, `base_url`, `auth`, `stream`, `options`.
Import it for type hints if you're wiring `parse_config`/`generate` into
your own tooling. `CodegenError` (from `polymo.codegen`) is the exception
`generate()` raises for configs it can't turn into a script; `ConfigError`
(from `polymo.config`, not re-exported at the top level) is what
`parse_config` raises for structurally invalid input.
