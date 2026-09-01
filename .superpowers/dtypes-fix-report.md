# dtypes preview schema-inference fix

## Status
Done. Committed to `main` (not pushed).

Commit: `4338367` — "fix(builder): preview schema inference matches generated scripts"

## Bug
`/api/sample`'s dtypes step (`_collect_records` → `_get_preview_df` in
`src/polymo/builder/app.py`) called `spark.createDataFrame(records)` with no
schema whenever `config.stream.schema` was unset, relying on Spark's own
type inference. That inference raises PySpark's
`[CANNOT_DETERMINE_TYPE] Some of types cannot be determined after inferring`
when any column is `None` in every sampled record — the common case for XML
APIs, where an always-empty element decodes to `None` (hit in practice with
Maileon).

## Fix
- Added `infer_ddl_from_records(records: list[dict]) -> str` and a shared
  `_infer_field_types` helper to `src/polymo/builder/preview.py`. Votes a
  Spark type per column using the same rules as the generated script's
  `_infer_schema` in `src/polymo/codegen/templates/core.py.jinja` (bool →
  BOOLEAN, int → BIGINT, float → DOUBLE, other → STRING; `None` casts no
  vote; `{BIGINT, DOUBLE}` merges to DOUBLE; any other conflict → STRING;
  field names backtick-quoted). Kept in sync via a code comment pointing at
  the template.
  - One deliberate divergence from the template, called out in the
    docstring: a column with **no** vote at all (all-`None`) defaults to
    STRING instead of being dropped from the DDL — the template's
    `_infer_schema` just omits such columns, which is fine for a generated
    script (it errors loudly on an empty sample) but would silently drop
    the column from the builder's dtypes UI, or (as here) crash outright
    when there's no schema at all to fall back on.
- `_get_preview_df` in `src/polymo/builder/app.py` now uses
  `infer_ddl_from_records`/`_infer_field_types` when `schema_ddl` is unset,
  instead of unqualified `createDataFrame(records)`.
- Nested dict/list values (JSON APIs) are `json.dumps`-encoded into a
  separate `safe_records` list before being handed to Spark under the
  inferred schema — mirrors the generated batch reader's `_cell` helper in
  `codegen/templates/dp.py.jinja`. Only applied in this no-explicit-schema
  path; the original `records` returned to the API response, and the
  explicit-schema path, are untouched.
- Extra fix found during TDD: `createDataFrame(data, schema=<DDL>)` verifies
  values strictly against the declared type (no int→double upcast), so a
  column merged to DOUBLE (int in one record, float in another) would raise
  `[FIELD_DATA_TYPE_UNACCEPTABLE_WITH_NAME]` unless the int values are
  coerced to `float` first. Added that coercion (bools excluded, since
  `bool` is an `int` subclass in Python).
- Empty `records` list: unchanged — `_collect_records` already short-circuits
  to `return records, []` before `_get_preview_df` is ever called.
- Records that carry no fields at all (e.g. all `{}`, so no DDL can be
  built): falls back to `spark.createDataFrame(records)` rather than
  building an invalid empty-DDL schema — a defensive edge case beyond the
  original bug report, not separately tested.

## Files changed
- `src/polymo/builder/preview.py` — added `_infer_field_types` and
  `infer_ddl_from_records`.
- `src/polymo/builder/app.py` — `_get_preview_df` uses the inferred schema
  path (JSON-encoding nested values, coercing ints under DOUBLE columns)
  instead of unqualified `createDataFrame`.
- `tests/test_web_app.py` — 4 new regression tests, using the existing
  `http_server` fixture pattern (`/api/sample` end-to-end against a real
  local Spark session, same as the pre-existing dtypes tests in this file):
  - `test_sample_endpoint_all_none_column_defaults_to_string`
  - `test_sample_endpoint_mixed_int_float_column_becomes_double`
  - `test_sample_endpoint_bool_column_becomes_boolean_not_bigint`
  - `test_sample_endpoint_nested_value_with_inferred_schema_becomes_json_string`

## Tests
Full suite: `354 passed` (ran with sandbox disabled — the `http_server`
fixture binds a local TCP socket, which the default sandbox denies).

```
354 passed, 1 warning in 62-63s
```

Pre-commit hooks (`ruff format`, `ruff check`) passed on commit.

## Where this landed
Fix is committed on `main` at `4338367` (not pushed, per instructions).
Nothing further needed from you — all 354 tests pass, ruff is clean, and
the four new regression tests cover the all-`None` column, mixed
int/float→double, bool-vs-bigint, and nested-dict-as-JSON-string cases from
the ticket.
