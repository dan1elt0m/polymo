# Polymo Codegen Phase 3 Implementation Plan (Runtime Deletion + 1.0.0)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Delete the 0.x runtime (Spark custom data source, RestClient, YAML/pydantic public config API), clean up every carry-over minor, rewrite the docs, and release polymo 1.0.0 as a pure dev-time code generator.

**Architecture:** The generator's only runtime dependency on the old code is `_render_template`/`_PathFormatter` — those move into `codegen/templating.py` first, then `datasource.py`, `rest_client.py`, `pydantic_config.py`, the YAML helpers, and the smoke script are deleted with their tests. Core dependencies shrink (httpx, pyyaml, fsspec, pyspark-adjacent extras reviewed). 0.11.0 is the tagged escape hatch for 0.x users; the migration doc says `pip install "polymo<1.0"`.

**Tech Stack:** unchanged (FastAPI builder, Jinja codegen, Vite frontend).

**Spec:** docs/superpowers/specs/2026-08-28-codegen-pivot-design.md ("Deletions" section)
**Carry-over:** docs/superpowers/plans/2026-08-28-phase1-carryover.md (both phases' deferred minors — Task 6 closes them)

## Global Constraints

- After this plan: `import polymo` exposes exactly `generate`, `CodegenError`, `parse_config`, `config_to_dict`, `RestSourceConfig` (plus dataclass types re-exported by `config.py` as today). No `ApiReader`, no `PolymoConfig`, no `load_config`/`dump_config`.
- `parse_config` (dict input) and `config_to_dict` survive — they are the builder/codegen contract. The version key check ("0.1") stays.
- Codegen behavior must not change: the golden files in `tests/codegen/golden/` must remain byte-identical through Tasks 1-5 (they may only change in Task 6 if a carry-over fix touches templates — reseed deliberately and say so).
- Full suite green after every task (`.venv/bin/python -m pytest tests/ -q`, sandbox off for sockets). Frontend rebuilds via `npm run build` at repo root.
- Version bump to 1.0.0 and the GitHub release happen ONLY in Task 8, after the final whole-branch review and the human's merge approval.

---

### Task 1: Move templating helpers into codegen

**Files:**
- Create: `src/polymo/codegen/templating.py`
- Modify: `src/polymo/codegen/generator.py` (imports)
- Test: `tests/codegen/` (existing suite is the net; add `tests/codegen/test_templating.py` with direct unit tests)

**Interfaces:**
- Produces: `polymo.codegen.templating._render_template(value, context)` and `_PathFormatter` with semantics byte-identical to the current `rest_client` versions (copy the code and its private helpers — the jinja env, env-var resolution, whatever `_render_template` transitively needs; read `rest_client.py` and pull the closure of definitions).
- `generator.py` imports change from `..rest_client` to `.templating`. `rest_client.py` itself is NOT modified (it dies in Task 3).

- [ ] **Step 1: Failing test** (`tests/codegen/test_templating.py`):
```python
from polymo.codegen.templating import _PathFormatter, _render_template


def test_render_template_resolves_options():
    ctx = {"options": {"country": "NL"}, "params": {}, "headers": {}, "raw_params": {}}
    assert _render_template("{{ options.country }}", ctx) == "NL"


def test_path_formatter_consumes_params():
    formatter = _PathFormatter({"user_id": "42", "limit": "5"})
    assert formatter.render("/users/{user_id}/posts") == "/users/42/posts"
    assert formatter.remaining_params() == {"limit": "5"}
```
- [ ] **Step 2: Run, verify fail** (ModuleNotFoundError). **Step 3:** copy the definitions, repoint `generator.py`. **Step 4:** full suite green; goldens unchanged (`git status tests/codegen/golden` clean). **Step 5: Commit** `refactor(codegen): move templating helpers out of rest_client`.

---

### Task 2: Delete the Spark custom data source

**Files:**
- Delete: `src/polymo/datasource.py`, `tests/test_datasource.py`
- Modify: `src/polymo/__init__.py` (drop `ApiReader` import/export and the whole `_alias_datasource` machinery), `src/polymo/codegen/generator.py` if it imports `_plan_partitions`-adjacent code (check: `_static_windows` was written to MIRROR datasource logic, not import it — verify with grep before deleting; if anything imports from `datasource`, inline it into codegen first)
- Test: new tombstone test in `tests/test_config.py` or a new `tests/test_public_api.py`

**Interfaces:**
- Produces: `tests/test_public_api.py` with:
```python
import pytest


def test_removed_runtime_symbols_are_gone():
    import polymo

    for name in ("ApiReader", "PolymoConfig", "load_config", "dump_config"):
        assert not hasattr(polymo, name)
    assert sorted(polymo.__all__) == sorted(
        ["generate", "CodegenError", "RestSourceConfig", "parse_config", "config_to_dict"]
    )


def test_runtime_modules_deleted():
    with pytest.raises(ModuleNotFoundError):
        import polymo.datasource  # noqa: F401
    with pytest.raises(ModuleNotFoundError):
        import polymo.rest_client  # noqa: F401
    with pytest.raises(ModuleNotFoundError):
        import polymo.pydantic_config  # noqa: F401
```
(The full assertions only pass after Tasks 3-4 — mark the not-yet-true parts `pytest.mark.xfail(strict=True)` per line or split into three tests added incrementally in Tasks 2/3/4; simplest: add only the `ApiReader`/`polymo.datasource` assertions now, extend the test in Tasks 3-4.)

- [ ] Steps: failing tombstone test → delete files → fix `__init__.py` (also add `CodegenError` to the public exports now) → full suite green (test_datasource.py removal drops its tests; count drops accordingly — note before/after counts in the report) → commit `feat!: remove the Spark custom data source (ApiReader)`.

---

### Task 3: Delete RestClient

**Files:**
- Delete: `src/polymo/rest_client.py`, `tests/test_rest_client.py`
- Modify: `pyproject.toml` — move `httpx` and `fsspec` out of core `dependencies` (grep first: `fsspec` is imported only by rest_client; `httpx` only by rest_client — confirm; `requests` must be ADDED where the builder preview needs it: the `builder` extra, since `preview.py` execs generated code that imports requests), `uv lock`
- Test: extend `tests/test_public_api.py` with the `polymo.rest_client` ModuleNotFoundError assertion

- [ ] Steps: `grep -rn "rest_client\|httpx\|fsspec" src/ tests/ --include="*.py" | grep -v tests/codegen` to enumerate every remaining reference (docs/config.md mentions are Task 7's problem); failing tombstone assertion → delete → dependency edits + `uv sync --extra builder --group dev` → full suite green → commit `feat!: remove RestClient; drop httpx/fsspec from core deps`.

---

### Task 4: Delete the YAML + pydantic public config API

**Files:**
- Delete: `src/polymo/pydantic_config.py`, `src/polymo/scripts/smoke.py` (+ `scripts/__init__.py` if empty), `docs/generate_config_doc.py`, `docs/polymo_config_reference.md`, `src/polymo/builder/static/examples/*.yml`, root `examples/*.yml` if present
- Modify: `src/polymo/config.py` (remove `load_config`, `dump_config`, `import yaml`; keep `parse_config`/`config_to_dict`/dataclasses), `src/polymo/__init__.py` (drop pydantic model exports), `src/polymo/cli.py` (drop the `smoke` subcommand and its import; `builder` remains the only subcommand), `.pre-commit-config.yaml` (remove the `generate-pydantic-docs` hook), `pyproject.toml` (drop `pyyaml` from core deps; drop the `smoke` extra and the `smoke` pytest marker), `tests/test_config.py` (rewrite YAML-based tests to dict-based `parse_config` calls — the semantics under test survive, only the input format changes; delete `load_config`/`dump_config`/PolymoConfig tests)
- Test: extend `tests/test_public_api.py` (pydantic_config tombstone, `load_config`/`dump_config` absence)

- [ ] Steps: enumerate references first (`grep -rn "pydantic_config\|PolymoConfig\|load_config\|dump_config\|smoke" src/ tests/ --include="*.py"`); failing tombstone assertions → delete/modify → `uv sync` → full suite green → `npm run build` still clean (frontend untouched but examples dir changed — confirm no `.yml` fetches remain: grep builder-ui/src for `.yml`) → commit `feat!: remove YAML and pydantic config APIs; polymo is a code generator`.

---

### Task 5: CLI and packaging sanity

**Files:**
- Modify: `src/polymo/cli.py` (final shape below), `pyproject.toml` (verify `[project.scripts]` entry, extras: `builder` extra must be self-sufficient — fastapi, uvicorn, requests, pyspark, pyarrow; `benchmark` extra: update or delete if it referenced the runtime — read it), `docs/cli.md` (rewrite: one command)
- Test: `tests/test_cli.py` (new)

**Interfaces:**
- `polymo builder [--host --port --reload]` is the only command. `main([])` with no subcommand prints help and returns 1.

- [ ] **Step 1: Failing test** (`tests/test_cli.py`):
```python
from polymo.cli import main


def test_no_command_shows_help(capsys):
    assert main([]) == 1
    assert "builder" in capsys.readouterr().out


def test_unknown_command_rejected():
    try:
        main(["smoke"])
        raise AssertionError("expected SystemExit")
    except SystemExit as exc:
        assert exc.code == 2
```
- [ ] Steps: run/fail → shrink cli.py (keep the uvicorn launch code path as-is; read it before editing) → `uv build` and `unzip -l dist/*.whl` to confirm no deleted modules ship and templates/static still do; clean dist/ → full suite green → commit `feat!: polymo CLI is builder-only`.

---

### Task 6: Carry-over cleanup batch (one dispatch, many small fixes)

**Files:** per item below — this is a batched task; every item is small and independent.
- `builder-ui/src/main.tsx`: remove the debug `return` that disables MSW in dev, and all leftover `console.log`s in builder-ui/src (grep; keep intentional error logging via console.error if any).
- `builder-ui/src/types.ts`: fix `RawPagePayload` to `{url: string; status_code: number; payload: unknown}` matching the backend.
- `builder-ui/src/lib/filename.ts`: delete the dead `slugifyName` export; have `App.tsx` use the shared helper instead of its private duplicate (one canonical slugifier).
- `builder-ui/src/App.tsx` (or CodePane): when the config has no `base_url` yet, show a neutral placeholder ("Fill in a base URL to see the generated script") instead of firing `/api/generate` and painting a 400 — gate the debounced effect on a non-empty base_url.
- `src/polymo/builder/app.py`: `SAMPLE_CONFIG_DICT` — drop the `__polymo_INITIAL_CONFIG__` template injection entirely (it is unread by the frontend; delete the constant if then unused, and the template line in `templates/index.html`).
- `tests/test_web_app.py`: add the missing test — a parse-valid-but-codegen-rejected config (streaming without schema) → `/api/generate` 400 with detail.
- Rebuild bundle (`npm run build`), commit rebuilt assets.

- [ ] Steps: implement all → `npx tsc -b --noEmit` + `npm run build` clean → full backend suite green → if any template/codegen file changed (it should NOT in this task), reseed goldens deliberately and flag it → commit `chore: close Phase 1/2 carry-over minors`.

---

### Task 7: Docs rewrite + migration guide

**Files:**
- Rewrite: `README.md` (polymo = dev-time script generator; quickstart: `uvx polymo builder` → click → export; the generated-script example from Phase 2 stays), `docs/index.md`, `docs/config.md` → repurpose as "Connector options reference" documenting the BUILDER's options and what code each option generates (keep the per-option explanations — pagination/auth/incremental/partitioning semantics are unchanged — but express them as builder options + generated-code behavior, not YAML)
- Create: `docs/migration-1.0.md` — covers: pin `polymo<1.0` (0.11.0 is the final 0.x); `spark.read.format("polymo")`, YAML configs, `PolymoConfig`, `load_config`/`dump_config`, `polymo smoke` all removed; how to rebuild an old YAML connector in the builder (open builder, re-enter settings — note there is deliberately no YAML importer, the JSON save format is the new WIP format); behavioral note from the Phase 1 rulings: endpoints-strategy scripts emit flat records without the 0.x `endpoint_name`/`data` wrapper.
- Modify: `docs/SUMMARY.md`/`mkdocs.yml` nav (drop polymo_config_reference, add migration), `docs/api.md` (public API = generate/parse_config/config_to_dict/RestSourceConfig/CodegenError), `docs/builder-ui.md` (remove any legacy-runtime references; check the gh-pages workflow still builds: `uvx --with mkdocs-material mkdocs build --strict` or whatever mkdocs.yml needs — read it)
- Test: `mkdocs build --strict` passes (broken nav/links fail it).

- [ ] Steps: grep docs/ for every mention of removed symbols → rewrite → `uv run --with mkdocs --with mkdocs-material mkdocs build --strict` (adapt to mkdocs.yml plugins) → commit `docs: 1.0 documentation and migration guide`.

---

### Task 8: Version 1.0.0 + final review gate

**Files:** `pyproject.toml` (version = "1.0.0"), `uv.lock`

- [ ] **Step 1:** Bump version, `uv lock`, full suite green, `uv build` + wheel inspection one last time.
- [ ] **Step 2:** Commit `release: polymo 1.0.0`.
- [ ] **Step 3:** STOP. The controller runs the final whole-branch review, then presents the merge decision to the human. The GitHub release (`gh release create 1.0.0`) happens only after the human approves the merge — never from this task.

---

### Task 9: XML response support (generator + builder) — user-requested, execute between Tasks 6 and 7

Motivation: Maileon (the first real data-team test case) serves `application/vnd.maileon.api+xml`; many enterprise APIs are XML-first. Generated scripts and the builder preview must be able to parse XML responses. Old 0.x runtime deliberately excluded (it is deleted by this plan).

**Files:**
- Modify: `src/polymo/config.py` (StreamConfig + parse/serialize), `src/polymo/codegen/generator.py`, `src/polymo/codegen/templates/core.py.jinja`, `builder-ui/src/types.ts`, `builder-ui/src/lib/transform.ts`, `builder-ui/src/components/builder/sections/BaseConfigurationSection.tsx` (or RecordSelectorSection — implementer's judgment), `tests/codegen/conftest.py` (mock server raw-body support)
- Test: `tests/codegen/test_xml.py`, golden case `maileon_xml` in `tests/codegen/test_golden.py`

**Interfaces:**
- Config: `StreamConfig.response_format: Literal["json", "xml"] = "json"` and `StreamConfig.xml_record_path: Optional[str] = None` (an `xml.etree.ElementTree` XPath selecting record elements, e.g. `.//contact`). `parse_config` reads `response_format`/`xml_record_path` from dicts; `config_to_dict` writes them. `xml_record_path` without `response_format: xml` is a ConfigError; `response_format: xml` without `xml_record_path` is a ConfigError.
- Codegen guards (CodegenError, in `generate_core`-reachable code so preview is guarded too — put them in `_context`): XML is incompatible with payload-path features — `cursor_path`, `next_url_path`, `total_pages_path`, `total_records_path`, and `record_selector.field_path` all raise (`"<feature> reads JSON paths and cannot be combined with response_format: xml"`). Header-based pagination (`total_pages_header`, `cursor_header`, `link_header`), offset/page/none pagination, record_filter (operates on built dicts), incremental, partitions, streaming (offset/page already enforced) all remain valid.
- Generated code, when xml: `import xml.etree.ElementTree as ET` (stdlib — the zero-extra-deps constraint holds); each fetch branch's `payload = response.json()` becomes `payload = ET.fromstring(response.content)`; `_records` is replaced by the XML variant:

```jinja
{% if response_format == "xml" %}
XML_RECORD_PATH = {{ xml_record_path_repr }}


def _records(root):
    """Flatten each matched XML element into a record dict."""
    records = []
    for element in root.findall(XML_RECORD_PATH):
        record = {f"@{key}": value for key, value in element.attrib.items()}
        for child in element:
            record[child.tag] = child.text
        records.append(record)
{% if record_filter_expr %}
    records = [record for record in records if ({{ record_filter_expr }})]
{% endif %}
    return records
{% else %}
... existing json _records ...
{% endif %}
```

- Mock server: extend `tests/codegen/conftest.py` so a route returning a `str`/`bytes` payload is sent raw with the route's headers (`Content-Type` from the headers dict, default `application/xml` for str/bytes) instead of json.dumps.
- Builder UI: a "Response format" select (JSON default / XML) plus an "XML record path" text input shown only when XML is selected; both transform directions; the CodePane 400 surface handles the incompatibility errors (no client-side duplication).

**Tests (execution, against the mock server):**
```python
def test_xml_records_parsed(http_server):
    body = (
        "<contacts>"
        "<contact id=\"7\"><email>a@b.nl</email><permission>NONE</permission></contact>"
        "<contact id=\"8\"><email>c@d.nl</email><permission>DOI</permission></contact>"
        "</contacts>"
    )
    http_server.routes["/contacts"] = lambda q, h, b: (200, body, {"Content-Type": "application/vnd.maileon.api+xml"})
    config = make_config(
        base_url=http_server.url, name="contacts", path="/contacts",
        response_format="xml", xml_record_path=".//contact",
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [
        {"@id": "7", "email": "a@b.nl", "permission": "NONE"},
        {"@id": "8", "email": "c@d.nl", "permission": "DOI"},
    ]
```
Plus: page pagination with `total_pages_header` + XML body (the Maileon shape, multi-page walk); guard tests for each incompatible combination (parametrized CodegenError/ConfigError); a `maileon_xml` golden (page_index/page_size/X-Pages, Authorization+Accept headers, xml_record_path `.//contact`); hygiene on all XML variants; JSON goldens byte-identical (only the `{% if %}` json arm is exercised by them — verify).

- [ ] Steps: TDD as usual → full suite → `npx tsc -b --noEmit` + `npm run build` → reseed only the NEW golden → commit `feat(codegen): XML response support` (+ separate `feat(builder-ui): response format selector` if you prefer two commits).

---

## Self-Review Notes

- Spec "Deletions" coverage: datasource (T2), rest_client (T3), YAML public interface + cli shrink (T4, T5). Docs (T7), release (T8). Carry-overs (T6).
- Deletion order is dependency-driven: templating move (T1) unblocks rest_client deletion (T3); datasource (T2) has no dependents after Phase 2.
- `parse_config` keeping `token`/`options` kwargs: the builder passes them (`_load_config_payload`) — untouched.
- Golden stability is a hard constraint through T5; T6 must not touch templates (its items are frontend/backend-app only).
- The 1.0.0 release is deliberately gated behind human approval in T8/finish — a breaking release is not the controller's call.
