# Polymo 1.4 Implementation Plan (Databricks Integration)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bundle-project export, CLI-backed deploy from the builder, and secret-scope references — per the approved spec.

**Architecture:** A new `polymo.codegen.bundle` module renders the project files by SPLITTING the existing generator output: `generate_core` output becomes `src/<pkg>/client.py`, the dp section becomes `pipelines/<stream>.py` with imports instead of same-module references. A new `polymo.builder.databricks` module wraps the CLI (argv subprocess, JSON, timeouts). New builder endpoints expose profiles/catalogs/schemas/scopes and bootstrap/deploy/run. Secrets become reference objects in the config schema, resolved by a generated `_dbx_secret` helper.

**Spec:** docs/superpowers/specs/2026-08-28-databricks-integration-design.md

## Global Constraints

- Secret values never in configs, generated files, endpoint responses, or logs. CLI calls: argv lists (never shell=True), `-o json`, `--profile` explicit, timeout ≤ 30s (deploy/run: 600s).
- All existing hygiene gates hold for every generated file (ast + ruff); goldens byte-stable except where a task reseeds deliberately.
- Existing single-file `generate()` behavior unchanged unless a task says otherwise; `/api/generate` contract unchanged.
- Tests never invoke the real `databricks` CLI — subprocess is faked (monkeypatch `subprocess.run` or inject a runner callable). A manual smoke with the real CLI happens in the final review only.
- Full suite green after every task (sandbox off). Frontend tasks: `npx tsc -b --noEmit` + `npm run build` + commit bundle.

---

### Task 1: Secret-scope references in config + codegen

**Files:** `src/polymo/config.py`, `src/polymo/codegen/generator.py`, `templates/core.py.jinja`, tests (`test_config.py`, new `tests/codegen/test_secret_refs.py`), `docs/config.md`.

**Interfaces:**
- Config schema: each secret slot accepts an optional reference object `{"scope": str, "key": str}`:
  - `auth.secret` for bearer/api_key/oauth2 (one slot each: token / api key / client secret),
  - `stream.option_secrets: {<option_name>: {"scope", "key"}}` for OPT_* placeholders.
  Dataclasses: `SecretRef(scope: str, key: str)` frozen; `AuthConfig.secret: SecretRef | None`; `StreamConfig.option_secrets: Mapping[str, SecretRef]`. parse/serialize both ways (references only). Validation: both fields non-empty; option_secrets keys must match scanned option refs is NOT required (unknown keys are ConfigError? no — allow, they're harmless; document).
- Codegen: when a slot has a SecretRef, the placeholder assignment becomes
  `API_KEY: str = _dbx_secret("scope", "key")` (same for API_TOKEN / CLIENT_SECRET / OPT_*), and the template emits ONE `_dbx_secret` helper (typed) when any ref exists:
  ```python
  def _dbx_secret(scope: str, key: str) -> str:
      """Resolve a Databricks secret on the driver."""
      try:
          from pyspark.dbutils import DBUtils  # type: ignore[import]
          from pyspark.sql import SparkSession

          session = SparkSession.getActiveSession()
          if session is None:
              raise RuntimeError("no active Spark session")
          return DBUtils(session).secrets.get(scope, key)
      except Exception as exc:  # noqa: BLE001
          raise RuntimeError(
              f"could not resolve Databricks secret {scope}/{key}: {exc}. "
              "Outside Databricks, replace this call with the literal value."
          ) from exc
  ```
  NOTE: this helper needs pyspark — but generate_core output must stay pyspark-free for preview! Resolution: the import is inside the function; the function is only CALLED at module level when a ref exists... which executes at exec-time in preview. Therefore: preview must intercept — run_preview already injects overrides AFTER exec... module-level `_dbx_secret(...)` call would run during exec and raise. RULING: emit the assignment lazily-overridable: `API_KEY: str = _dbx_secret("scope", "key")` is correct for production, and `run_preview`/`run_generated` must SOURCE-SUBSTITUTE overrides BEFORE exec (the run_generated helper already does source-level substitution since the OPT_ work — extend `run_preview` in `src/polymo/builder/preview.py` the same way: replace the `_dbx_secret("scope", "key")` call-site text for the overridden variable with the literal token before exec, or simpler: pre-exec, replace line `API_KEY: str = _dbx_secret(...)` with `API_KEY: str = "<token>"` via regex on the variable name). Add preview tests for a secret-ref config with a session token.
- Hygiene: scripts with refs pass ast+ruff; mypy note: helper imports guarded.

Steps: TDD (parse/serialize round-trip, ConfigError cases, codegen emission for all four slot kinds, preview override test, hygiene) → implement → goldens: add `secret_scope_bearer` golden; existing goldens byte-identical → commit `feat: Databricks secret-scope references`.

---

### Task 2: Bundle project generator

**Files:** Create `src/polymo/codegen/bundle.py`, `templates/bundle/databricks.yml.jinja`, `templates/bundle/pipeline.py.jinja`, `templates/bundle/readme.md.jinja`; modify `generator.py` only if splitting needs a context tweak. Tests: `tests/codegen/test_bundle.py` + golden dir `tests/codegen/golden_bundle/`.

**Interfaces:**
- `generate_bundle(config: RestSourceConfig, *, project_name: str, catalog: str, schema: str) -> dict[str, str]` returning relpath→content:
  - `databricks.yml`: bundle name = sanitized project_name; one pipeline resource (`resources.pipelines.<key>`) with `catalog: <catalog>`, `schema/target: <schema>` (use the CURRENT Lakeflow bundle schema — the implementer runs `databricks bundle init` (default-python, non-interactive flags or the lakeflow-pipelines template) in a scratch dir to capture today's canonical shape and mirrors it; if init needs network and fails, fall back to the documented schema from `databricks bundle schema` which is offline), `libraries: - glob` / root_path per the canonical template so `src/` imports work; targets: `dev` (default, `mode: development`) and `prod`.
  - `src/<pkg>/__init__.py` (empty or re-export), `src/<pkg>/client.py` = EXACTLY `generate_core(config)` output (byte-identical — assert in tests) plus nothing else.
  - `pipelines/<stream>.py` = the dp section, transformed: `from <pkg>.client import fetch_records, ...` — enumerate the names the dp section references from core (fetch_records, _infer_schema when present, WINDOWS, _write_state, _records/fetch_page for streaming, API placeholders NOT needed there) — implement by rendering the dp template with an `imports_from` context instead of assuming same-module globals; sys.path note: the canonical bundle template makes `src/` importable for pipeline files (mirror exactly how; if it uses a `sys.path.append` shim in the pipeline file, emit that).
  - `README.md`: 15 lines — what it is, `databricks bundle deploy -t dev`, where the table lands.
- `<pkg>` = `_identifier(project_name)`; `<stream>` = existing func_name.
- Constraint: client.py byte-equals generate_core(config) (single source of truth — preview/export/bundle can never drift).

Steps: TDD (bundle dict keys; client.py byte-equality; pipeline file hygiene (ast+ruff) and imports resolve statically (compile with a stubbed package? at minimum ast + "from <pkg>.client import" present); databricks.yml parses as YAML (pyyaml via dev dep? pyyaml was removed — use `uv run --with pyyaml` in a subprocess-free way: add pyyaml to DEV group only, justified for tests) → golden bundle (full file set for the jsonplaceholder config, byte-compared) → commit `feat(codegen): Databricks Asset Bundle project generator`.

---

### Task 3: CLI wrapper + read endpoints

**Files:** Create `src/polymo/builder/databricks.py`; modify `src/polymo/builder/app.py`; tests `tests/test_databricks_endpoints.py`.

**Interfaces:**
- `databricks.py`: `run_cli(args: list[str], *, profile: str | None, timeout: float = 30.0, runner=subprocess.run) -> Any` (json.loads stdout; raises `DatabricksCliError` with stderr detail; `FileNotFoundError` → "databricks CLI not found — install: https://docs.databricks.com/dev-tools/cli"). `list_profiles() -> list[str]` parses `~/.databrickscfg` section names with configparser (no CLI needed; missing file → []).
- Endpoints (GET): `/api/databricks/profiles` → `{profiles: [...]}`; `/api/databricks/catalogs?profile=` → CLI `catalogs list -o json` → `{catalogs: [name...]}`; `/api/databricks/schemas?profile=&catalog=` → `schemas list <catalog> -o json`; `/api/databricks/secret-scopes?profile=` → `secrets list-scopes -o json`; `/api/databricks/secret-keys?profile=&scope=` → `secrets list-secrets <scope> -o json`. Errors → HTTP 502 `{detail}` (CLI missing → 501 `{detail}` so the UI can distinguish "install the CLI").
- Tests: fake runner injected (app factory or monkeypatch) covering happy path, CLI-missing, CLI-error, and that profile lands in argv; NEVER a real subprocess.

Steps: TDD → implement → commit `feat(builder): Databricks CLI read endpoints`.

---

### Task 4: Bootstrap / deploy / run endpoints

**Files:** `src/polymo/builder/app.py`, `src/polymo/builder/databricks.py`; tests extend `tests/test_databricks_endpoints.py`.

**Interfaces:**
- `POST /api/databricks/bootstrap` `{config_dict, project_dir, project_name, catalog, schema, overwrite?: bool}` → writes `generate_bundle` files under project_dir/project_name; refuses existing non-empty dir unless overwrite; response `{project_path, files: [...]}`. Path safety: expanduser, absolute-ize; refuse writing inside the polymo package dir.
- `POST /api/databricks/deploy` `{project_path, profile, target="dev"}` → `databricks bundle deploy -t <target>` with cwd=project_path, 600s timeout; response `{ok, output}` (stdout+stderr tail, secrets never present by construction).
- `POST /api/databricks/run` `{project_path, profile, target}` → `bundle run <pipeline_key> -t <target>`; pipeline_key read from the project's databricks.yml (parse with pyyaml dev-only? runtime needs it → read the key by regex or store a `.polymo-bundle.json` manifest written at bootstrap listing the key — RULING: write `.polymo-bundle.json` manifest at bootstrap `{pipeline_key, stream, generated_by}` and read that; no yaml dep at runtime).
- Tests: fake runner asserts argv/cwd; bootstrap writes expected files (tmp_path), overwrite refusal, path-safety rejection.

Steps: TDD → implement → commit `feat(builder): bootstrap and deploy endpoints`.

---

### Task 5: Frontend — Deploy panel + secret pickers

**Files:** `builder-ui/src/components/DeployPanel.tsx` (new), `lib/api.ts`, `atoms/index.ts`, `App.tsx`, `AuthenticationSection.tsx` (+ the OPT placeholder surface if one exists in the UI — check), `types.ts`, `lib/transform.ts`, `mocks/handlers.ts`.

**Interfaces:**
- Deploy panel (new third tab "Deploy" next to UI Builder / Generated Code): profile select (loads on open; empty state explains ~/.databrickscfg), catalog select (loads per profile), schema select (per catalog), project name (default = table name), project directory text input (default `~/polymo-projects/<name>`), buttons: Bootstrap → Deploy → Run (sequential enablement: deploy needs a bootstrapped path, run needs a deploy), monospace output area appending each call's output/errors. 501 from backend → install-CLI message inline.
- Secret pickers: in AuthenticationSection, for bearer/api_key/oauth2, a "Secret source" toggle: "enter at deploy time (placeholder)" vs "Databricks secret scope" → scope select + key select (fetched per profile — reuse the profile chosen in Deploy panel via a shared atom; if none chosen yet, prompt to pick profile first). Emits `auth.secret` ref in the config; round-trips via configToFormState. (option_secrets UI: only if an OPT surface already exists — otherwise leave config-only and note it.)
- All new fetches follow api.ts postJson/getJson conventions; msw handlers extended so `npm run dev` works.

Steps: read current tab/atom wiring → implement → tsc + build clean → manual smoke via TestClient-backed uvicorn (report what's verified; full click-through best-effort) → commit `feat(builder-ui): Deploy panel and secret-scope pickers` (+ bundle).

---

### Task 6: Single-file export keeps up + docs

**Files:** `App.tsx`/CodePane (export menu gains "Download bundle project (.zip)"? — RULING: v1 the bundle is written via the Bootstrap button only; the CodePane download stays single-file. Just ensure the single-file script still handles secret refs — Task 1 covered codegen; verify a doc note), `docs/builder-ui.md`, `docs/config.md`, `README.md`, `docs/migration-1.0.md` untouched.

- Docs: new "Deploy to Databricks" section (profile/catalog/schema flow, bundle layout, CLI requirement, secret scopes incl. AKV-backed note); config reference gains `auth.secret` + `option_secrets`; README quickstart gains the deploy step. mkdocs strict build.
- Commit `docs: Databricks deploy and secret scopes`.

---

### Task 7: Version 1.4.0 + final gate

- Bump version, uv lock, full suite, wheel sanity (bundle templates included in wheel!). Commit `release: polymo 1.4.0`. STOP — controller runs final whole-branch review + REAL-CLI manual smoke (bootstrap a project for the jsonplaceholder config, `databricks bundle validate` with Daniel's default profile — read-only validate, NO deploy), then the human gates the release.

## Self-Review Notes

- Spec coverage: secrets (T1), bundle (T2), CLI reads (T3), bootstrap/deploy/run (T4), UI (T5), docs (T6), release (T7). Single-file export preserved (T1/T6). One-connector-per-project honored (T2).
- The preview-vs-_dbx_secret interception (T1) is the riskiest seam — T1 must add an explicit preview test.
- pyyaml returns as a DEV-group-only dependency for bundle tests (T2); runtime reads the manifest json instead (T4).
