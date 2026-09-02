# Lean generated code — implementation report

Four requested cleanups to polymo's *generated* output (single-file scripts
and Databricks Asset Bundle projects), plus the reference/test/doc updates
that follow from them.

## 1. Minimal comments in generated output

- `core.py.jinja` (single-file `client.py`/script core): removed every
  explanatory `#` comment — secret-store guidance ("Fill in your token...
  fetch it from a secret store, e.g. `dbutils.secrets.get(...)`"), the
  commented-out truststore opt-in block, the WINDOWS/"records are not
  tagged" notes, the streaming/preview placeholder explanations, the
  option-placeholder guidance block. Kept only the two genuinely load-bearing
  hygiene pragmas: `# noqa: E402` on `dp.py.jinja`'s imports (they still
  follow code in the single concatenated script — restructuring that away
  would mean moving pyspark imports into the core template unconditionally,
  a much bigger change than this task's scope) and `# type: ignore[import]`
  on the two guarded `pyspark`/`azure` imports inside `_dbx_secret`/
  `_uc_secret` (must stay local/guarded so preview keeps working without
  pyspark installed).
- `bundle/pipeline.py.jinja`: dropped its `# noqa: E402` entirely — bundle
  pipeline files already have all imports at the top of the file (nothing
  precedes them but the module docstring), so the pragma was dead weight.
  Also moved `bundle/source.py.jinja`'s `pyspark.sql.datasource` import up
  to the top of the file (it used to sit after `SCHEMA`/
  `_apply_secret_options`), eliminating its `# noqa: E402` too.
- Docstrings: every generated `.py` file keeps exactly a one-line module
  docstring (`"""Lakeflow Declarative Pipelines connector for <stream>."""`,
  `"""Spark DataSource for <stream>."""`, `"""Lakeflow Declarative Pipeline
  for <stream>."""`) and one-line docstrings survive only on the three named
  public entry points — `fetch_records` (varies by pagination strategy),
  the `get_token` OAuth2 helper, and (implicitly, since none were ever
  emitted) the `DataSource` classes. Every private helper (`_dbx_secret`,
  `_uc_secret`, `_request`, `_dig`, `_records`, `_infer_schema`, `_cell`,
  `_rebuild_option_literals`, `fetch_page`, `_apply_secret_options`) lost
  its docstring.
- `databricks.yml.jinja`, `pyproject.toml.jinja`: all comments removed.
  `readme.md.jinja`: kept as brief prose, no tool-name mention (item 4).
- New test `tests/codegen/test_lean_output.py`: for every golden `.py` file
  (single-file + bundle) and a 9-config sweep covering secret refs (scope
  and UC, on auth and on `OPT_*` option placeholders), windows, incremental
  state, streaming, and XML — no line's stripped form starts with `#`, and
  no `#` appears mid-line except `# noqa...`/`# type: ignore...` (a
  same-line `#` inside a quoted string literal is excluded from the check,
  since none of those are comments).
- Removed `_comment_escape`/`stream_name_comment` from `generator.py`
  entirely — with the last comment that interpolated a config value gone
  (the STATE_PATH "e.g. a Databricks Volume" note), nothing in the
  generated output uses `#`-comment escaping any more, so the helper was
  dead code. Updated `test_escaping.py`'s newline-injection regression test
  to target the one place a raw stream name can still land verbatim — the
  one-line module docstring (`_doc_escape`, unaffected) — instead of the
  now-nonexistent comment.

## 2. Pipeline file visible in the Databricks project view

`bundle/databricks.yml.jinja`'s pipeline resource now sets
`root_path: ${workspace.file_path}` (the bundle project root) instead of
`root_path: src`. The `libraries: - glob: include: pipelines/<stream>.py`
glob is unchanged — with `root_path` now covering the whole project,
`databricks.yml`, `src/`, and `pipelines/<stream>.py` all show up under the
pipeline's root in the Databricks UI, instead of the pipeline file
appearing to sit outside the project. This was always safe: the wheel
(`environment.dependencies`) is what makes `src/<pkg>` importable on the
driver and every executor, not `root_path` — `root_path` only ever affected
`sys.path` for resolving the `pipelines/<stream>.py` glob and what the
Databricks pipeline-editor UI treats as project root.

Validated offline (`databricks` CLI v0.269.0, unauthenticated, per the task
brief):
- `databricks bundle schema` confirms a pipeline resource's `root_path` is
  a plain string field (no format restriction) — `${workspace.file_path}`
  is exactly the pattern the reference `axon_bronze.pipeline.yaml` uses for
  the same field, just without stream's `/src/axon` suffix (not needed
  here — `src/<pkg>` reaches every executor via the wheel, not via
  `root_path`).
- Bootstrapped a full generated bundle project (`generate_bundle(...)`
  written to a tmp dir) and ran `databricks bundle validate -t dev` against
  it: fails only with `databricks-cli auth: a new access token could not be
  retrieved` (the expected outcome per the task brief — CLI installed,
  unauthenticated) — zero schema/YAML validation errors.
- `tests/codegen/test_bundle.py::test_databricks_yml_parses_with_expected_resource_keys`
  updated to assert the new `root_path` value.

## 3. No REPLACE_ME for secret-ref slots in bundles

In bundle mode (`for_bundle=True`), a secret-ref-backed slot (auth
`API_TOKEN`/`API_KEY`/`CLIENT_SECRET`, or any ref-backed `OPT_*` option
placeholder) now renders as `<VAR>: str | None = None` instead of
`"REPLACE_ME"`. A slot with **no** ref still gets `"REPLACE_ME"` — that
placeholder means "the user needs to type a value here", which stays
correct; a ref-backed slot's "no value yet" state means "the pipeline
forgot to resolve and install this", which is a bug, not a fill-in-the-blank
— `"REPLACE_ME"` there would silently ship the literal string to the real
API instead of failing loudly.

Every point that actually reads such a slot at call time now guards it:

```python
if API_TOKEN is None:
    raise RuntimeError(
        "API_TOKEN was not installed by the pipeline — resolve secrets on"
        " the driver and pass them as reader options"
    )
```

- Auth slots (`API_TOKEN`/`API_KEY`/`CLIENT_SECRET`): guarded right before
  first use in whichever single `fetch_records`/`fetch_page` variant the
  config renders, and at the top of `get_token()` for `CLIENT_SECRET`.
- `OPT_*` option placeholders embedded in `PATH`/`PARAMS`/`HEADERS`: these
  can't be guarded at their own assignment (that literal is evaluated once,
  at import time, before the pipeline has had any chance to install a
  secret) — they're guarded inside `_rebuild_option_literals()` instead,
  right before it re-evaluates the literals that embed them; this function
  is always called (from `_apply_secret_options`, in bundle-mode
  `source.py`) before any real fetch happens, in both `schema()` and
  `reader()`/`simpleStreamReader()`.
- `generator._context` computes this per slot via `_auth_secret_rhs`
  (returns `(rhs, type_annotation, optional)`) and a mirrored
  `_option_placeholder_spec`; `rebuild_guard_vars` narrows the OPT_*
  guard list to exactly the ref-backed vars actually embedded in whichever
  of PATH/PARAMS/HEADERS need rebuilding. Single-file mode
  (`for_bundle=False`) is completely unaffected — those slots keep
  resolving directly via `_dbx_secret(...)`/`_uc_secret(...)` at import
  time, same as before.

`bundle/source.py.jinja`'s `_apply_secret_options` needed no logic change
(`setattr` unconditionally overwrites the slot regardless of its prior
`None`/`"REPLACE_ME"` value) — only the option-key prefix rename (item 4).

Extended `tests/codegen/test_bundle.py`'s three executor-wheel simulations
(real subprocesses, a built wheel, a real mock HTTP server) with the new
semantics:
- `test_bundle_wheel_secret_ref_resolved_driver_side_and_shipped_via_options`:
  positive case unchanged (option installs the value, request carries it);
  negative case (no option supplied) now asserts the subprocess exits
  non-zero with `RuntimeError: API_TOKEN was not installed...` in stderr,
  and that no second request ever reached the mock server — instead of the
  old "request goes out with `Bearer REPLACE_ME`" assertion.
- `test_bundle_wheel_option_placeholders_in_headers_and_params_resolved` and
  `test_bundle_wheel_option_placeholder_in_path_resolved`: same shape —
  negative control now asserts a non-zero exit and the exact
  `RuntimeError` message (naming `OPT_TEAM_ID`/`OPT_TENANT_ID`
  respectively — `rebuild_guard_vars` is alphabetically sorted, so
  `OPT_TEAM_ID`'s guard fires first when both are unresolved) instead of a
  successful request carrying `"REPLACE_ME"`.
- `test_client_diverges_from_generate_core_when_secret_ref_present`:
  updated to assert `"API_TOKEN: str | None = None"` instead of the old
  `'API_TOKEN: str = "REPLACE_ME"'`.

## 4. No "polymo" in generated code

- Renamed the DataSource option prefix `polymo_secret_` → `secret_`
  everywhere it's used: `bundle/pipeline.py.jinja` (`_secret_options = {f"secret_{key}": ...}`)
  and `bundle/source.py.jinja` (`_apply_secret_options`'s `prefix`), plus
  every `tests/codegen/test_bundle.py` executor-simulation assertion that
  constructs or checks that option key.
- Purged every other "polymo" mention from generated `.py`/`.yml`/`.toml`/
  README content: module docstrings ("generated by the polymo builder" →
  e.g. `"""Lakeflow Declarative Pipelines connector for <stream>."""`),
  `bundle/readme.md.jinja`'s "Databricks Asset Bundle generated by polymo
  for..." (→ "Databricks Asset Bundle for the `<stream>` stream.") and its
  "no polymo import at runtime" bullet (→ just "fetch/schema code").
  `databricks.yml.jinja`'s and `pyproject.toml.jinja`'s explanatory
  comments (which mentioned polymo) are gone entirely per item 1 anyway.
- Kept the one explicit exception: `.polymo-bundle.json`'s filename and its
  `generated_by: "polymo <version>"` field (`codegen/bundle.py`'s
  `generate_bundle`, untouched) — the Deploy tab's "Run on Databricks" flow
  needs this to recognise its own projects.
- New test coverage in `test_lean_output.py`: every golden bundle file
  content except `.polymo-bundle.json` (plus every golden single-file
  script) is asserted case-insensitively `"polymo" not in content.lower()`;
  a 9-config sweep re-generates and re-checks both single-file and bundle
  output the same way; a dedicated positive test confirms the manifest
  *does* still carry `"polymo"`.

## Goldens reseeded

Deleted and regenerated every golden fixture (`tests/codegen/golden/*.py`,
9 single-file cases spanning every auth type + both secret-ref kinds +
XML/streaming/windows/incremental; `tests/codegen/golden_bundle/**`, the
full JSONPlaceholder bundle project). Spot-read several by hand
(`oauth_incremental_partitioned.py`, `secret_scope_bearer.py`,
`uc_secret_bearer.py`, `streaming_page.py`, the golden bundle's
`client.py`/`source.py`/`pipelines/posts.py`/`databricks.yml`/`README.md`,
plus a fresh XML+api_key+retries combo not in any golden) — all read as
clean, ordinary hand-written Python/YAML/Markdown with zero tool
attribution.

## Docs

`docs/config.md`:
- Bearer Token bullet and the incremental "State path" section: dropped
  "(the generated comment shows a Databricks example)" — that comment no
  longer exists; replaced with a direct example inline.
- Rewrote both "At deploy time" paragraphs (Databricks secret-scope and UC
  service-credential sections). They previously claimed `src/<pkg>/client.py`
  is "exactly the same `generate_core()` output..., `_dbx_secret` call
  included" for a secret-ref config — that was already stale before this
  task (bundle mode has never baked a direct `_dbx_secret(...)` call into
  `client.py`; the `for_bundle=True` REPLACE_ME behavior predates this
  change). Now accurately describes the `str | None` slot,
  `pipelines/<stream>.py` resolving driver-side and threading the value
  through as a `secret_<name>` reader option, and the `RuntimeError` guard
  if a slot is never installed.

`docs/builder-ui.md`: reviewed for `polymo_secret_`/comment-block/
REPLACE_ME-with-refs mentions — none found needing a change (its one
REPLACE_ME mention describes the *no-ref* default, unaffected by item 3;
the `_dbx_secret`/`_uc_secret` mentions link out to config.md, now
accurate, for the full mechanics). No edit made.

## Preview compatibility (verified, not changed)

`src/polymo/builder/preview.py`'s `run_preview` calls `generate_core(config)`
with no `for_bundle` argument (defaults `False`) — single-file mode is
completely untouched by item 3, so `_substitute_secret_refs`'s regex still
matches `<VAR>: str = _dbx_secret(...)`/`_uc_secret(...)` assignment lines
exactly as before. Verified directly: generated a bearer+secret-ref core,
confirmed the regex matches and both the no-token and real-token
substitution paths still produce `API_TOKEN: str = "REPLACE_ME"` /
`API_TOKEN: str = "my-real-token"`. The new `str | None = None` bundle-mode
output never reaches preview at all.

## Verification

- `pytest -q` (sandbox disabled, needed for the `http_server` fixture's
  socket bind): **435 passed**, 0 failed, run twice back to back (goldens
  stable both times — no drift on a second generation).
- `pytest tests/codegen -q` inside the sandbox (no network): 194 passed
  (everything that doesn't need `http_server`); goldens seeded on first
  run, matched byte-for-byte on rerun.
- `ruff check .`: all checks passed (repo-wide, including every changed
  template/test file and the reseeded goldens — `pyproject.toml`'s
  `[tool.ruff] extend-exclude` still excludes the golden dirs from ruff's
  own formatting opinions, but `assert_hygiene`, which every golden test
  calls, runs ruff against the actual generated string at test time).
- `mypy` spot-check (via `uvx mypy --ignore-missing-imports`, mypy isn't a
  project dependency) on four representative generated files: a plain
  single-file script, a bundle `client.py` with a bearer secret ref
  (`str | None` + guard), and a bundle `client.py` with query-placed
  api_key secret ref + two ref-backed `OPT_*` option placeholders
  (`_rebuild_option_literals` + guards) — all four: **Success: no issues
  found**.
- `databricks bundle schema` + `databricks bundle validate -t dev` against
  a bootstrapped tmp copy of a generated bundle project — see item 2 above;
  fails only on auth, no schema errors.

## Concerns / follow-ups

- None blocking. One judgment call worth flagging: `docs/config.md`'s "At
  deploy time" sections were already inaccurate before this task (the
  by-reference-pickling/wheel fix that made bundle mode diverge from
  `generate_core()` for secret refs predates this session, per
  `test_client_diverges_from_generate_core_when_secret_ref_present`'s own
  docstring) — I corrected them as part of item 3's "update REPLACE_ME-with-refs
  prose" instruction rather than leaving the pre-existing drift in place.
- `tests/codegen/test_lean_output.py`'s stray-`#`-comment scanner uses a
  cheap quote-balance heuristic to skip a `#` that's inside a string
  literal (e.g. `"5XX"`-style retry-status text, none of which currently
  contain `#`, but future config values might). It's a heuristic, not a
  full tokenizer — fine for this test's purpose (nothing in current
  templates trips it either way, verified), but worth knowing if a future
  template change ever embeds a literal `#` inside a string on the same
  line as something that looks like a real comment.
