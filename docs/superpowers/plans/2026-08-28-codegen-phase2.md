# Polymo Codegen Phase 2 Implementation Plan (Builder Rewire)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The builder becomes an assistant around the Phase 1 generator: its preview executes the generated code, the YAML pane becomes a read-only generated-code pane with copy/download, and YAML disappears from the user-facing surface.

**Architecture:** Backend: new `/api/generate` returns the script for a config dict; `/api/sample` execs `generate_core` output in-process (with a `_request` wrapper capturing raw pages) instead of using `RestClient`; `/api/format` and YAML-string payloads are removed. Frontend (Vite/React in `builder-ui/`, compiled into `src/polymo/builder/static/`): form state stays the source of truth; the YAML derivation is replaced by a debounced `/api/generate` call rendered in a read-only code pane; work-in-progress saves as JSON; a streaming toggle is added. The frontend build toolchain was never committed and must be reconstructed first.

**Tech Stack:** FastAPI, Jinja codegen (Phase 1), Vite + React 18 + TypeScript + Tailwind + Radix + Jotai + MSW, pytest + fastapi TestClient.

**Spec:** docs/superpowers/specs/2026-08-28-codegen-pivot-design.md
**Carry-over context:** docs/superpowers/plans/2026-08-28-phase1-carryover.md

## Global Constraints

- Generated scripts import ONLY `requests`, stdlib, and (dp section) `pyspark`; output passes `ast.parse` + `ruff check` (Phase 1 gates stay green).
- The preview MUST execute the same code the export produces (`generate_core` output) — no second fetch engine. `RestClient` may no longer be imported by `src/polymo/builder/app.py` when this phase completes.
- Secrets: session token/client secret are preview-only overrides injected into the exec namespace; they never appear in generated scripts or server logs.
- YAML: no user-facing YAML when this phase completes (js-yaml removed from the frontend; `/api/format` and `config`-string payloads removed from the backend). `parse_config`/YAML python API remains for Phase 3 to delete.
- Frontend builds must emit exactly `src/polymo/builder/static/main.js` and `main.css` (unhashed names — index.html references them directly).
- Run backend tests with `.venv/bin/python -m pytest`; frontend build with `npm --prefix builder-ui run build`.
- Preview exec of generated code runs arbitrary-looking generated Python in the builder process. That is by design (dev tool, user's own machine, same trust level as running the export). Never exec user-typed strings directly — always the generator's output for a validated config.

---

### Task 1: Reconstruct the frontend build toolchain

**Files:**
- Create: `builder-ui/package.json`, `builder-ui/vite.config.ts`, `builder-ui/tsconfig.json`, `builder-ui/tailwind.config.ts`, `builder-ui/postcss.config.js`
- Test: `npm --prefix builder-ui run build` output + existing backend test `tests/test_web_app.py` still green

**Interfaces:**
- Produces: a committed, reproducible `npm run build` that emits `src/polymo/builder/static/main.js` + `main.css` loadable by `src/polymo/builder/templates/index.html`.

- [ ] **Step 1: Write the configs.** External imports in `builder-ui/src` are exactly: `react`, `react-dom`, `jotai`, `js-yaml`, `clsx`, `@radix-ui/react-select`, `@radix-ui/react-tabs`, `msw`. `builder-ui/package.json`:

```json
{
  "name": "polymo-builder-ui",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "msw": "msw init public --save"
  },
  "dependencies": {
    "@radix-ui/react-select": "^2.1.0",
    "@radix-ui/react-tabs": "^1.1.0",
    "clsx": "^2.1.0",
    "jotai": "^2.9.0",
    "js-yaml": "^4.1.0",
    "react": "^18.3.0",
    "react-dom": "^18.3.0"
  },
  "devDependencies": {
    "@types/js-yaml": "^4.0.9",
    "@types/react": "^18.3.0",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.0",
    "autoprefixer": "^10.4.0",
    "msw": "^2.4.0",
    "postcss": "^8.4.0",
    "tailwindcss": "^3.4.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0"
  }
}
```

`builder-ui/vite.config.ts` (fixed output names into the python package):

```ts
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/polymo/builder/static",
    emptyOutDir: false,
    rollupOptions: {
      output: {
        entryFileNames: "main.js",
        assetFileNames: (info) =>
          info.name?.endsWith(".css") ? "main.css" : "[name][extname]",
      },
    },
  },
});
```

`tsconfig.json`: standard Vite react-ts template (`"jsx": "react-jsx"`, `"strict": true`, `"moduleResolution": "bundler"`, include `src`). Tailwind config with `content: ["./index.html", "./src/**/*.{ts,tsx}"]`; postcss with tailwindcss+autoprefixer. Check `builder-ui/src/styles/index.css` for `@tailwind` directives to confirm Tailwind version assumptions; adapt if it uses plain CSS.

- [ ] **Step 2: Install and build.** `npm --prefix builder-ui install`, then `npm --prefix builder-ui run build`. Fix compile errors pragmatically (missing type packages, tsconfig strictness) — do NOT rewrite app code beyond what compilation requires; if `tsc --noEmit` drowns in pre-existing strictness errors, drop `tsc` from the build script and note it in the report.

- [ ] **Step 3: Verify the bundle serves.** `git stash` nothing — instead compare: start the builder (`.venv/bin/python -m uvicorn polymo.builder.app:create_app --factory --port 8899`), `curl -s localhost:8899 | grep main.js`, and fetch `/static/main.js` (200, non-trivial size). Backend tests: `.venv/bin/python -m pytest tests/test_web_app.py -q`.

- [ ] **Step 4: Commit** `builder-ui/package.json`, `package-lock.json`, `vite.config.ts`, `tsconfig.json`, tailwind/postcss configs, and the rebuilt `static/main.js`/`main.css` if they differ: `git commit -m "build(builder-ui): reconstruct and commit the frontend toolchain"`.

---

### Task 2: `/api/generate` endpoint

**Files:**
- Modify: `src/polymo/builder/app.py`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Produces: `POST /api/generate` with body `{"config_dict": {...}}` → `{"script": "<python>", "stream": "<name>"}`; 400 with detail on `ConfigError`/`CodegenError`.

- [ ] **Step 1: Failing tests** (append to `tests/test_web_app.py`, matching its existing TestClient style):

```python
def test_generate_returns_script(client):
    payload = {"config_dict": SAMPLE_CONFIG_DICT}
    response = client.post("/api/generate", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["stream"] == "posts"
    assert "from pyspark import pipelines as dp" in body["script"]
    assert "import polymo" not in body["script"]


def test_generate_rejects_invalid_config(client):
    response = client.post("/api/generate", json={"config_dict": {"version": "0.1"}})
    assert response.status_code == 400
```

(Reuse the module's existing `client` fixture/`SAMPLE_CONFIG_DICT` import pattern — read the test file first and follow it.)

- [ ] **Step 2: Run, verify fail.** `pytest tests/test_web_app.py -q` → 404 on the new route.

- [ ] **Step 3: Implement** in `app.py`:

```python
from ..codegen import CodegenError, generate


class GenerateRequest(BaseModel):
    config_dict: Dict[str, Any]
    model_config = ConfigDict(extra="ignore")


class GenerateResponse(BaseModel):
    script: str
    stream: str


@app.post("/api/generate", response_model=GenerateResponse)
async def generate_script(payload: GenerateRequest) -> GenerateResponse:
    try:
        config = parse_config(payload.config_dict)
        script = generate(config)
    except (ConfigError, CodegenError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return GenerateResponse(script=script, stream=config.stream.name)
```

- [ ] **Step 4: Tests pass** (full suite). **Step 5: Commit** `feat(builder): /api/generate endpoint`.

---

### Task 3: Preview executes the generated code

**Files:**
- Create: `src/polymo/builder/preview.py`
- Modify: `src/polymo/builder/app.py` (rewrite `_collect_rest_preview`; drop `RestClient`/`PaginationWindow` imports)
- Test: `tests/test_web_app.py` (existing `/api/sample` tests must pass unchanged), new `tests/test_builder_preview.py`

**Interfaces:**
- Produces: `run_preview(config: RestSourceConfig, *, token: str | None, limit: int) -> tuple[list[dict], list[dict]]` returning `(records, raw_pages)`; raw_pages entries shaped like today's (`{"url": ..., "status_code": ..., "payload": ...}` — read `_collect_rest_preview` first and preserve the exact keys the frontend consumes).
- Consumes: `generate_core(config)` from Phase 1.

- [ ] **Step 1: Failing test** (`tests/test_builder_preview.py`, using the mock server fixture style from `tests/codegen/conftest.py` — import or copy the fixture):

```python
def test_preview_executes_generated_code(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}, {"id": 2}], {})
    config = make_config(base_url=http_server.url)
    records, raw_pages = run_preview(config, token=None, limit=1)
    assert records == [{"id": 1}]          # limit respected
    assert raw_pages[0]["status_code"] == 200
    assert raw_pages[0]["url"].endswith("/posts")


def test_preview_injects_bearer_token(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Bearer tok-1"
        return 200, [{"id": 1}], {}
    http_server.routes["/posts"] = route
    config = make_config(base_url=http_server.url, auth=AuthConfig(type="bearer"))
    records, _ = run_preview(config, token="tok-1", limit=5)
    assert records == [{"id": 1}]
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement `preview.py`:**

```python
"""Run the generated fetch core in-process for builder previews."""

from __future__ import annotations

from itertools import islice
from typing import Any, Dict, List, Optional, Tuple

from ..codegen import generate_core
from ..config import RestSourceConfig


def run_preview(
    config: RestSourceConfig, *, token: Optional[str], limit: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    code = generate_core(config)
    namespace: Dict[str, Any] = {}
    exec(compile(code, "<polymo-preview>", "exec"), namespace)  # noqa: S102

    if token:
        namespace["API_TOKEN"] = token       # bearer
        namespace["CLIENT_SECRET"] = token   # oauth2 (harmless if unused)

    raw_pages: List[Dict[str, Any]] = []
    original_request = namespace["_request"]

    def recording_request(session, url, params):
        response = original_request(session, url, params)
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        raw_pages.append(
            {"url": str(response.url), "status_code": response.status_code, "payload": payload}
        )
        return response

    namespace["_request"] = recording_request
    records = list(islice(namespace["fetch_records"](), limit))
    return records, raw_pages
```

Then rewrite `_collect_rest_preview` in `app.py` to call `run_preview` (map exceptions to the same `(raw_pages, rest_error)` contract it has today), and delete the `RestClient`/`PaginationWindow` imports. The `_collect_records` Spark-dtypes path keeps working — read how it builds a DataFrame today; if it goes through `ApiReader`, switch it to `spark.createDataFrame(records)` from the preview records so the builder no longer depends on the datasource for preview dtypes. Preserve the exact response shapes of `/api/sample`.

If the existing raw_pages contract includes fields this wrapper can't know (read the code first), adapt the wrapper — the frontend (`SamplePreview.tsx`) is the consumer of record.

- [ ] **Step 4: All tests pass, including the pre-existing `/api/sample` tests.** **Step 5: Commit** `feat(builder): preview executes the generated script`.

---

### Task 4: Remove `/api/format` and YAML-string payloads

**Files:**
- Modify: `src/polymo/builder/app.py`, `tests/test_web_app.py`

**Interfaces:**
- Produces: `/api/validate` and `/api/sample` accept `config_dict` only (`config: str` field and its YAML parsing removed); `/api/format` route deleted; `ValidationResponse.yaml` field dropped.

- [ ] **Step 1: Update tests first**: delete `/api/format` tests; change any test posting YAML `config` strings to post `config_dict`; add `test_yaml_payload_rejected` asserting a payload with only a `config` string now 422s. Run: failures confirm current behavior.
- [ ] **Step 2: Implement**: remove `FormatRequest`/`FormatResponse`/`format_config`, the `config: Optional[str]` fields on `ValidationRequest`/`SampleRequest` (keep `config_dict` required), `_load_config_payload`'s YAML-string branch, and the `yaml` field on `ValidationResponse`. `import yaml` should disappear from `app.py` if now unused; `SAMPLE_CONFIG` module constant may stay YAML-sourced internally or become a dict literal — make it a dict literal (`SAMPLE_CONFIG_DICT` directly) so `app.py` no longer imports yaml at all.
- [ ] **Step 3: Full suite green.** **Step 4: Commit** `feat(builder)!: config payloads are dict-only; /api/format removed`.

---

### Task 5: Frontend — generated-code pane replaces YAML

**Files:**
- Create: `builder-ui/src/components/CodePane.tsx`
- Modify: `builder-ui/src/lib/api.ts` (add `generateScript`), `builder-ui/src/atoms/index.ts`, `builder-ui/src/App.tsx`
- Delete: `builder-ui/src/components/YamlEditor.tsx`, `builder-ui/src/lib/yaml.ts`, `builder-ui/src/lib/pysparkExport.ts`, `builder-ui/src/types/js-yaml.d.ts`; drop `js-yaml` + `@types/js-yaml` from package.json

**Interfaces:**
- Consumes: `POST /api/generate` (Task 2).
- Produces: `generateScript(configDict): Promise<{script: string; stream: string}>` in api.ts (same fetch conventions as the existing `validate`/`sample` helpers — read them first); `CodePane` renders the script read-only in a `<pre><code>` with Copy (navigator.clipboard) and Download buttons (Blob download named `<stream>.py`); a jotai atom holding `{script, error, loading}` refreshed with a 400ms debounce whenever the form-state config dict changes (follow how YAML derivation is wired today in atoms/App and replace that flow).

- [ ] **Step 1: Read before writing**: `App.tsx` (how the YAML pane/tab is mounted and how form state → config dict flows through `lib/transform.ts`), `atoms/index.ts`, `lib/api.ts`, `components/YamlEditor.tsx`. Map every import of the deleted modules (`grep -rn "yaml\|pysparkExport" builder-ui/src`).
- [ ] **Step 2: Implement** the api helper, atom, and `CodePane.tsx`; replace the YAML editor mount in `App.tsx` with `CodePane`; render backend 400 details (CodegenError text) inside the pane as the error state — this is how users learn a combo is unsupported. Remove all deleted-module imports. Keep styling consistent with the existing pane (reuse its container classes).
- [ ] **Step 3: Build**: `npm --prefix builder-ui run build` clean; `grep -c "js-yaml" builder-ui/package.json` → 0.
- [ ] **Step 4: Manual smoke** via the running builder: form change updates the pane; copy/download works (verify the download button produces a `.py` named after the stream by inspecting the anchor's `download` attribute in the DOM — no browser automation required, `curl` + reading the built JS is insufficient, use the dev server or a quick Playwright-less check in the report).
- [ ] **Step 5: Commit** `feat(builder-ui)!: generated-code pane replaces YAML editor`.

---

### Task 6: Frontend — JSON save/load of work-in-progress

**Files:**
- Modify: `builder-ui/src/App.tsx` (or the component that owned YAML import/export — find it in Step 1), `builder-ui/src/components/LandingScreen.tsx` if it offers YAML import

**Interfaces:**
- Produces: "Save config" downloads `{"version": "0.1", ...config_dict}` as `<stream>.polymo.json`; "Load config" file-picker parses JSON and hydrates the form state via the existing state-setting path (find how LandingScreen/App hydrate state from a config today — likely the reverse transform in `lib/transform.ts` — and reuse it).

- [ ] **Step 1: Read** how import/export worked with YAML (LandingScreen + App) and what reverse transform exists (`configToFormState` or similar in transform.ts).
- [ ] **Step 2: Implement** JSON download/upload against the config dict; delete YAML import affordances.
- [ ] **Step 3: Build clean; manual smoke: save → reload → load → identical form state (compare config dicts).**
- [ ] **Step 4: Commit** `feat(builder-ui): JSON save/load for work-in-progress configs`.

---

### Task 7: Frontend — streaming toggle

**Files:**
- Modify: `builder-ui/src/types.ts`, `builder-ui/src/lib/transform.ts`, `builder-ui/src/components/builder/sections/BaseConfigurationSection.tsx` (or a better-fitting section — implementer's judgment), `builder-ui/src/mocks/handlers.ts` if it validates payload shapes

**Interfaces:**
- Produces: a "Streaming table" toggle mapping to `stream.streaming: true` in the config dict (matching `StreamConfig.streaming` from Phase 1). Unsupported combos need no client-side logic: the `/api/generate` 400 detail (from the Phase 1 guards) already surfaces in the CodePane error state (Task 5) — verify that path shows, e.g., "streaming requires ... schema" when toggled without a schema.

- [ ] Steps: read section components for the toggle idiom → add field to BuilderState + transform (both directions) → build clean → manual smoke (toggle on with page pagination + schema shows a script containing `SimpleDataSourceStreamReader`; toggle without schema shows the CodegenError in the pane) → commit `feat(builder-ui): streaming toggle`.

---

### Task 8: Rebuild, backend smoke, docs

**Files:**
- Modify: `src/polymo/builder/static/main.js`, `main.css` (rebuilt), `docs/builder-ui.md`, `README.md`, `docs/config.md`
- Test: `tests/test_web_app.py`

**Interfaces:**
- Produces: committed production bundle; docs describing the new flow.

- [ ] **Step 1:** Final `npm --prefix builder-ui run build`; commit the bundle.
- [ ] **Step 2:** Add one backend test asserting `GET /` serves and `/static/main.js` exists and contains `"/api/generate"` (bundle really is the new UI).
- [ ] **Step 3:** Docs: `docs/builder-ui.md` — rewrite the workflow (form → live generated dp script → copy/download; JSON save/load; streaming toggle; no YAML). `README.md` — replace the "What's coming in 1.0" note with a "The builder generates standalone scripts" section showing a 10-line example of generated output. `docs/config.md` — mark YAML sections as legacy/0.x (deletion happens in Phase 3; don't delete docs yet, banner them).
- [ ] **Step 4:** Full backend suite green. **Step 5: Commit** `docs: builder generates standalone dp scripts`.

---

## Self-Review Notes

- Spec coverage (Phase 2 section of spec): preview-executes-generated-code (T3), read-only code pane + copy/download (T5), `/api/format` removed + dict-only payloads (T4), `/api/generate` (T2), JSON save/load (T6), `PolymoConfig`/`parse_config` stay internal (untouched — Phase 3). Streaming toggle (T7) closes the Phase 1 gap that `streaming` had no UI. Toolchain reconstruction (T1) is a prerequisite discovered post-spec (package.json never committed).
- Frontend tasks direct implementers to read the named files first and reuse existing idioms rather than transcribe speculative code — the exact component internals were not visible when this plan was written; interfaces and behavior contracts above are binding, internal wiring follows the codebase's existing patterns.
- Type consistency: `run_preview` (T3) is consumed only by `app.py`; `generateScript` (T5) consumed by T5/T7 smoke steps; `stream.streaming` key matches Phase 1's `StreamConfig.streaming`.
- Playwright e2e (builder-ui/tests) intentionally out of scope: no committed Playwright config; revisit in Phase 3 polish.
