# Polymo Codegen Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A `polymo.codegen` module that turns a `RestSourceConfig` into a standalone Lakeflow Declarative Pipelines script (zero polymo imports) covering every existing runtime feature.

**Architecture:** `generate_core(config)` renders a pure-Python fetch script (requests only, exec-able for preview/tests); `generate(config)` appends the `dp` wiring. Jinja templates with feature blocks; only blocks the config uses are emitted. Static facts (windows, params, schema) are expanded to literals at generation time.

**Tech Stack:** Python ≥3.10, jinja2 (already a dep), pytest, ruff (dev), stdlib `http.server` for execution tests.

**Spec:** `docs/superpowers/specs/2026-08-28-codegen-pivot-design.md`

## Global Constraints

- Generated scripts import ONLY `requests`, stdlib, and (in the dp section) `pyspark`. Never `polymo`, `jinja2`, `httpx`, `yaml`.
- Generated output must pass `ast.parse` and `ruff check` (helpers below run both in every execution test).
- `generate_core` output must not import pyspark (it is exec'd in-process by builder preview).
- Jinja env: `StrictUndefined`, `trim_blocks=True`, `lstrip_blocks=True`, `keep_trailing_newline=True`.
- Secrets: never a real token in output; bearer emits `API_TOKEN = "REPLACE_ME"` + key-vault comment. The builder's session token is preview-only.
- Config source of truth is the existing `RestSourceConfig` dataclasses in `src/polymo/config.py` — do not change their semantics, only add `streaming: bool = False` to `StreamConfig` (Task 12).
- Every task: TDD (failing test first), commit at the end. Run tests with `.venv/bin/python -m pytest`.

---

### Task 1: Scaffold codegen + test infrastructure + baseline script

**Files:**
- Create: `src/polymo/codegen/__init__.py`, `src/polymo/codegen/generator.py`, `src/polymo/codegen/templates/core.py.jinja`, `src/polymo/codegen/templates/dp.py.jinja`
- Create: `tests/codegen/__init__.py`, `tests/codegen/conftest.py`, `tests/codegen/helpers.py`, `tests/codegen/test_baseline.py`
- Modify: `pyproject.toml` (add `ruff>=0.6` to `[dependency-groups] dev`)

**Interfaces:**
- Produces: `generate(config: RestSourceConfig) -> str`, `generate_core(config: RestSourceConfig) -> str`, `CodegenError(Exception)`; test helpers `run_generated(config) -> SimpleNamespace` (execs core, returns namespace), `assert_hygiene(code: str)`, `make_config(**overrides) -> RestSourceConfig`, `http_server` fixture with `.url`, `.routes` dict, `.log` list.

- [ ] **Step 1: Write the failing test**

`tests/codegen/helpers.py`:
```python
from __future__ import annotations

import ast
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

from polymo.codegen import generate_core
from polymo.config import AuthConfig, RestSourceConfig, StreamConfig


def make_config(
    *,
    base_url: str,
    auth: AuthConfig | None = None,
    options: dict[str, Any] | None = None,
    **stream_kwargs: Any,
) -> RestSourceConfig:
    stream_kwargs.setdefault("name", "posts")
    stream_kwargs.setdefault("path", "/posts")
    return RestSourceConfig(
        version="0.1",
        base_url=base_url,
        auth=auth or AuthConfig(),
        stream=StreamConfig(**stream_kwargs),
        options=options or {},
    )


def assert_hygiene(code: str) -> None:
    ast.parse(code)
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "--no-cache", "--stdin-filename", "gen.py", "-"],
        input=code.encode(),
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()


def run_generated(config: RestSourceConfig) -> SimpleNamespace:
    code = generate_core(config)
    assert_hygiene(code)
    namespace: dict[str, Any] = {}
    exec(compile(code, "<generated>", "exec"), namespace)  # noqa: S102
    return SimpleNamespace(**namespace)
```

`tests/codegen/conftest.py`:
```python
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

import pytest


class MockApi:
    def __init__(self) -> None:
        self.routes = {}
        self.log = []
        self.url = ""


@pytest.fixture
def http_server():
    api = MockApi()

    class Handler(BaseHTTPRequestHandler):
        def _respond(self) -> None:
            parsed = urlparse(self.path)
            api.log.append((self.command, self.path, dict(self.headers)))
            route = api.routes.get(parsed.path)
            if route is None:
                self.send_response(404)
                self.end_headers()
                return
            query = {k: v[-1] for k, v in parse_qs(parsed.query).items()}
            body_len = int(self.headers.get("Content-Length") or 0)
            body = self.rfile.read(body_len) if body_len else b""
            status, payload, headers = route(query, dict(self.headers), body)
            data = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for key, value in headers.items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(data)

        do_GET = _respond
        do_POST = _respond

        def log_message(self, *args) -> None:  # silence
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    api.url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield api
    server.shutdown()
```

`tests/codegen/test_baseline.py`:
```python
from __future__ import annotations

from polymo.codegen import generate, generate_core
from tests.codegen.helpers import assert_hygiene, make_config, run_generated


def test_core_fetches_single_page(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}, {"id": 2}], {})
    config = make_config(base_url=http_server.url)

    module = run_generated(config)

    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]


def test_core_has_no_forbidden_imports():
    config = make_config(base_url="https://api.example.com")
    core = generate_core(config)
    for forbidden in ("polymo", "pyspark", "jinja2", "yaml", "httpx"):
        assert f"import {forbidden}" not in core


def test_full_script_appends_dp_wiring():
    config = make_config(base_url="https://api.example.com")
    script = generate(config)
    assert_hygiene(script)
    assert script.startswith(generate_core(config))
    assert "from pyspark import pipelines as dp" in script
    assert "@dp.table(name=\"posts\")" in script
    assert "def posts()" in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'polymo.codegen'`

- [ ] **Step 3: Implement**

Add to `pyproject.toml` `[dependency-groups] dev`: `"ruff>=0.6",` then run `uv sync --extra builder --group dev`.

`src/polymo/codegen/__init__.py`:
```python
from .generator import CodegenError, generate, generate_core

__all__ = ["CodegenError", "generate", "generate_core"]
```

`src/polymo/codegen/generator.py`:
```python
"""Render standalone Lakeflow Declarative Pipelines scripts from a config."""

from __future__ import annotations

import re
from typing import Any, Dict

from jinja2 import Environment, PackageLoader, StrictUndefined

from ..config import RestSourceConfig


class CodegenError(Exception):
    """Raised when a config cannot be expressed as a generated script."""


_ENV = Environment(
    loader=PackageLoader("polymo.codegen", "templates"),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def _identifier(name: str) -> str:
    cleaned = re.sub(r"\W", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned


def _context(config: RestSourceConfig) -> Dict[str, Any]:
    stream = config.stream
    return {
        "base_url": config.base_url.rstrip("/"),
        "path": stream.path,
        "params_repr": repr(dict(stream.params or {})),
        "headers_repr": repr(dict(stream.headers or {})),
        "stream_name": stream.name,
        "func_name": _identifier(stream.name),
    }


def generate_core(config: RestSourceConfig) -> str:
    return _ENV.get_template("core.py.jinja").render(**_context(config))


def generate(config: RestSourceConfig) -> str:
    return generate_core(config) + "\n\n" + _ENV.get_template("dp.py.jinja").render(
        **_context(config)
    )
```

`src/polymo/codegen/templates/core.py.jinja`:
```jinja
"""{{ stream_name }} — generated by the polymo builder.

Standalone Lakeflow Declarative Pipelines source. polymo is NOT needed
at runtime; edit this file freely.
"""

import requests

BASE_URL = "{{ base_url }}"
PATH = "{{ path }}"
PARAMS: dict = {{ params_repr }}
HEADERS: dict = {{ headers_repr }}
TIMEOUT = 30.0

# Behind a corporate TLS-intercepting proxy? `pip install truststore`
# and uncomment the next two lines:
# import truststore
# truststore.inject_into_ssl()


def _records(payload):
    """Normalise a response payload to a list of dicts."""
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = [payload]
        for key in ("data", "items", "results"):
            if key in payload and isinstance(payload[key], list):
                records = payload[key]
                break
    else:
        records = [payload]
    return [r if isinstance(r, dict) else {"record": r} for r in records]


def fetch_records():
    """Yield records from the API, one page at a time."""
    session = requests.Session()
    session.headers.update(HEADERS)
    response = session.get(f"{BASE_URL}{PATH}", params=PARAMS, timeout=TIMEOUT)
    response.raise_for_status()
    yield from _records(response.json())
```

`src/polymo/codegen/templates/dp.py.jinja`:
```jinja
from pyspark import pipelines as dp
from pyspark.sql import SparkSession

spark = SparkSession.getActiveSession()


@dp.table(name="{{ stream_name }}")
def {{ func_name }}():
    return spark.createDataFrame(list(fetch_records()))
```

Also add `"src/polymo/codegen/templates/*.jinja"` to package data if `pyproject.toml` doesn't already include package data (hatchling includes all files under src by default — verify with `uv build && unzip -l dist/*.whl | grep jinja`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add src/polymo/codegen tests/codegen pyproject.toml uv.lock
git commit -m "feat(codegen): scaffold generator with baseline dp script"
```

---

### Task 2: Record selector block (field_path, filter, cast note)

**Files:**
- Modify: `src/polymo/codegen/generator.py`, `src/polymo/codegen/templates/core.py.jinja`
- Test: `tests/codegen/test_record_selector.py`

**Interfaces:**
- Consumes: Task 1 helpers.
- Produces: context keys `field_path` (list or None), `record_filter_expr` (python expr str or None). Generated `_records(payload)` gains selector behavior. `cast_to_schema_types` is handled by the dp section's explicit schema (Task 10), not here.

- [ ] **Step 1: Write the failing tests**

`tests/codegen/test_record_selector.py`:
```python
from __future__ import annotations

import pytest

from polymo.codegen import CodegenError, generate_core
from polymo.config import RecordSelectorConfig
from tests.codegen.helpers import make_config, run_generated


def test_field_path_with_wildcard(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        {"data": {"eu": [{"id": 1}], "us": [{"id": 2}]}},
        {},
    )
    config = make_config(
        base_url=http_server.url,
        record_selector=RecordSelectorConfig(field_path=["data", "*"]),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]


def test_record_filter_translated_to_python(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [{"id": 1, "ok": True}, {"id": 2, "ok": False}],
        {},
    )
    config = make_config(
        base_url=http_server.url,
        record_selector=RecordSelectorConfig(record_filter="{{ record['ok'] }}"),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1, "ok": True}]


def test_invalid_filter_raises_codegen_error():
    config = make_config(
        base_url="https://x",
        record_selector=RecordSelectorConfig(record_filter="{{ record[ }}"),
    )
    with pytest.raises(CodegenError):
        generate_core(config)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/test_record_selector.py -v`
Expected: first two FAIL (records not selected/filtered), third FAIL (no error raised)

- [ ] **Step 3: Implement**

In `generator.py` add:
```python
import ast as _ast


def _filter_expression(record_filter: str | None) -> str | None:
    if not record_filter:
        return None
    expr = record_filter.strip()
    if expr.startswith("{{") and expr.endswith("}}"):
        expr = expr[2:-2].strip()
    try:
        _ast.parse(expr, mode="eval")
    except SyntaxError as exc:
        raise CodegenError(
            f"record_filter is not a supported expression: {record_filter!r}"
        ) from exc
    return expr
```
Extend `_context` with:
```python
        "field_path": list(stream.record_selector.field_path) or None,
        "record_filter_expr": _filter_expression(stream.record_selector.record_filter),
```

In `core.py.jinja` replace the `_records` body with:
```jinja
def _records(payload):
    """Normalise a response payload to a list of dicts."""
{% if field_path %}
    current = [payload]
    for segment in {{ field_path }}:
        next_level = []
        for item in current:
            if segment == "*":
                if isinstance(item, list):
                    next_level.extend(item)
                elif isinstance(item, dict):
                    next_level.extend(item.values())
            elif isinstance(item, dict) and segment in item:
                next_level.append(item[segment])
        current = next_level
    records = []
    for item in current:
        records.extend(item if isinstance(item, list) else [item])
{% else %}
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = [payload]
        for key in ("data", "items", "results"):
            if key in payload and isinstance(payload[key], list):
                records = payload[key]
                break
    else:
        records = [payload]
{% endif %}
    records = [r if isinstance(r, dict) else {"record": r} for r in records]
{% if record_filter_expr %}
    records = [record for record in records if ({{ record_filter_expr }})]
{% endif %}
    return records
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): record selector field_path and filter blocks"
```

---

### Task 3: Retries/backoff block (always emitted, values inlined)

**Files:**
- Modify: `src/polymo/codegen/generator.py`, `templates/core.py.jinja`
- Test: `tests/codegen/test_retries.py`

**Interfaces:**
- Produces: generated `_request(session, url, params)` used by all later pagination blocks; context keys `max_retries`, `retry_status_snippet`, `initial_delay`, `max_delay`, `multiplier`, `retry_on_timeout`, `retry_on_connection_errors`.

- [ ] **Step 1: Write the failing test**

`tests/codegen/test_retries.py`:
```python
from __future__ import annotations

from itertools import count

from polymo.config import BackoffConfig, ErrorHandlerConfig
from tests.codegen.helpers import make_config, run_generated


def test_retries_5xx_then_succeeds(http_server):
    attempts = count()
    http_server.routes["/posts"] = lambda q, h, b: (
        (500, {"err": "boom"}, {}) if next(attempts) < 2 else (200, [{"id": 1}], {})
    )
    config = make_config(
        base_url=http_server.url,
        error_handler=ErrorHandlerConfig(
            max_retries=3,
            backoff=BackoffConfig(initial_delay_seconds=0.0, max_delay_seconds=0.0),
        ),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}]
    assert len(http_server.log) == 3


def test_status_not_retryable_raises(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (404, {"err": "nope"}, {})
    config = make_config(base_url=http_server.url)
    module = run_generated(config)
    try:
        list(module.fetch_records())
        raise AssertionError("expected HTTPError")
    except Exception as exc:  # requests.HTTPError, but namespace-local
        assert "404" in str(exc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/test_retries.py -v`
Expected: FAIL — first test sees HTTPError after 1 attempt (no retry loop yet)

- [ ] **Step 3: Implement**

`_context` additions (translate `ErrorHandlerConfig`; turn `("5XX", "429")` into a python condition string):
```python
def _retry_condition(retry_statuses) -> str:
    checks = []
    for spec in retry_statuses:
        if spec.endswith("XX"):
            base = int(spec[0]) * 100
            checks.append(f"{base} <= status <= {base + 99}")
        else:
            checks.append(f"status == {int(spec)}")
    return " or ".join(checks) or "False"
```
Context keys: `max_retries=eh.max_retries`, `retry_condition=_retry_condition(eh.retry_statuses)`, `initial_delay=eh.backoff.initial_delay_seconds`, `max_delay=eh.backoff.max_delay_seconds`, `multiplier=eh.backoff.multiplier`, `retry_on_timeout=eh.retry_on_timeout`, `retry_on_connection_errors=eh.retry_on_connection_errors` where `eh = stream.error_handler`.

Template: add `import time` under `import requests`, then before `_records`:
```jinja
MAX_RETRIES = {{ max_retries }}


def _should_retry(status):
    return {{ retry_condition }}


def _request(session, url, params):
    """GET with retries: statuses ({{ retry_condition }}), backoff x{{ multiplier }}."""
    delay = {{ initial_delay }}
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = session.get(url, params=params, timeout=TIMEOUT)
        except requests.exceptions.Timeout:
            if not {{ retry_on_timeout }} or attempt == MAX_RETRIES:
                raise
        except requests.exceptions.ConnectionError:
            if not {{ retry_on_connection_errors }} or attempt == MAX_RETRIES:
                raise
        else:
            if not _should_retry(response.status_code) or attempt == MAX_RETRIES:
                response.raise_for_status()
                return response
        time.sleep(delay)
        delay = min(delay * {{ multiplier }}, {{ max_delay }}) if {{ max_delay }} > 0 else delay * {{ multiplier }}
    raise RuntimeError("unreachable")
```
Replace the `session.get(...)` + `raise_for_status()` pair in `fetch_records` with `response = _request(session, f"{BASE_URL}{PATH}", PARAMS)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): inline retry/backoff helper"
```

---

### Task 4: Offset pagination

**Files:**
- Modify: `generator.py`, `templates/core.py.jinja`
- Test: `tests/codegen/test_pagination_offset.py`

**Interfaces:**
- Produces: `fetch_records` template becomes a `{% if pagination_type == ... %}` dispatch; context keys `pagination_type`, `page_size`, `limit_param`, `offset_param`, `start_offset`, `stop_on_empty`.

- [ ] **Step 1: Write the failing test**

`tests/codegen/test_pagination_offset.py`:
```python
from __future__ import annotations

from polymo.config import PaginationConfig
from tests.codegen.helpers import make_config, run_generated


def test_offset_pagination_walks_until_empty(http_server):
    def route(query, headers, body):
        offset = int(query.get("offset", "0"))
        assert query.get("limit") == "2"
        data = {0: [{"id": 1}, {"id": 2}], 2: [{"id": 3}]}.get(offset, [])
        return 200, data, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="offset", page_size=2, limit_param="limit", offset_param="offset"
        ),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert len(http_server.log) == 3  # 2 full pages + 1 short page stops
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/codegen/test_pagination_offset.py -v`
Expected: FAIL — only one request made (baseline single-page fetch)

- [ ] **Step 3: Implement**

Context additions: `pagination_type=stream.pagination.type`, plus `page_size`, `limit_param`, `offset_param`, `start_offset`, `stop_on_empty=stream.pagination.stop_on_empty_response`. In `core.py.jinja` replace `fetch_records` with a dispatch:
```jinja
{% if pagination_type == "offset" %}
def fetch_records():
    """Yield records, paginating with {{ offset_param }}/{{ limit_param }}."""
    session = requests.Session()
    session.headers.update(HEADERS)
    offset = {{ start_offset }}
    while True:
        params = dict(PARAMS)
{% if limit_param and page_size %}
        params["{{ limit_param }}"] = {{ page_size }}
{% endif %}
        params["{{ offset_param }}"] = offset
        response = _request(session, f"{BASE_URL}{PATH}", params)
        records = _records(response.json())
        if not records:
            return
        yield from records
        step = {{ page_size if page_size else "len(records)" }}
        if len(records) < step:
            return
        offset += step
{% elif pagination_type == "none" %}
def fetch_records():
    """Yield records from the API (single page)."""
    session = requests.Session()
    session.headers.update(HEADERS)
    response = _request(session, f"{BASE_URL}{PATH}", PARAMS)
    yield from _records(response.json())
{% endif %}
```
(The `offset_param or "offset"` default from the runtime: apply in `_context`, not the template: `offset_param=stream.pagination.offset_param or "offset"`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): offset pagination block"
```

---

### Task 5: Page pagination (with total_pages stop conditions)

**Files:**
- Modify: `generator.py`, `templates/core.py.jinja`
- Test: `tests/codegen/test_pagination_page.py`

**Interfaces:**
- Produces: context keys `page_param`, `start_page`, `total_pages_path` (list|None), `total_pages_header` (str|None); generated `_dig(payload, path)` helper shared with cursor pagination (Task 6).

- [ ] **Step 1: Write the failing tests**

`tests/codegen/test_pagination_page.py`:
```python
from __future__ import annotations

from polymo.config import PaginationConfig
from tests.codegen.helpers import make_config, run_generated


def test_page_pagination_stops_on_short_page(http_server):
    def route(query, headers, body):
        page = int(query.get("page", "1"))
        data = {1: [{"id": 1}, {"id": 2}], 2: [{"id": 3}]}.get(page, [])
        return 200, data, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(type="page", page_size=2, page_param="page"),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_page_pagination_respects_total_pages_path(http_server):
    def route(query, headers, body):
        page = int(query.get("page", "1"))
        return 200, {"meta": {"pages": 2}, "results": [{"p": page}]}, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="page", page_param="page", total_pages_path=("meta", "pages")
        ),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"p": 1}, {"p": 2}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/test_pagination_page.py -v`
Expected: FAIL (template has no `page` branch → jinja renders `none` branch, single request)

- [ ] **Step 3: Implement**

Context: `page_param=stream.pagination.page_param or "page"`, `start_page`, `total_pages_path=list(...) or None`, `total_pages_header`. Emit `_dig` (before `_records`) whenever `total_pages_path` or (Task 6) `cursor_path`/`next_url_path` is set:
```jinja
def _dig(payload, path):
    """Follow a key path into a JSON payload; None if any hop is missing."""
    current = payload
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current
```
Add the `page` branch to the `fetch_records` dispatch:
```jinja
{% elif pagination_type == "page" %}
def fetch_records():
    """Yield records, paginating with {{ page_param }}."""
    session = requests.Session()
    session.headers.update(HEADERS)
    page = {{ start_page }}
    while True:
        params = dict(PARAMS)
{% if limit_param and page_size %}
        params["{{ limit_param }}"] = {{ page_size }}
{% endif %}
        params["{{ page_param }}"] = page
        response = _request(session, f"{BASE_URL}{PATH}", params)
        payload = response.json()
        records = _records(payload)
        if not records:
            return
        yield from records
{% if total_pages_path %}
        total = _dig(payload, {{ total_pages_path }})
        if total is not None and page >= int(total):
            return
{% elif total_pages_header %}
        total = response.headers.get("{{ total_pages_header }}")
        if total is not None and page >= int(total):
            return
{% else %}
{% if page_size %}
        if len(records) < {{ page_size }}:
            return
{% endif %}
{% endif %}
        page += 1
{% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): page pagination block with total_pages stops"
```

---

### Task 6: Cursor pagination (cursor_path / cursor_header / next_url_path / initial_cursor)

**Files:**
- Modify: `generator.py`, `templates/core.py.jinja`
- Test: `tests/codegen/test_pagination_cursor.py`

**Interfaces:**
- Produces: context keys `cursor_param`, `cursor_path`, `cursor_header`, `next_url_path`, `initial_cursor`.

- [ ] **Step 1: Write the failing tests**

`tests/codegen/test_pagination_cursor.py`:
```python
from __future__ import annotations

from polymo.config import PaginationConfig
from tests.codegen.helpers import make_config, run_generated


def test_cursor_from_payload_path(http_server):
    def route(query, headers, body):
        cursor = query.get("cursor")
        if cursor is None:
            return 200, {"data": [{"id": 1}], "next": "abc"}, {}
        assert cursor == "abc"
        return 200, {"data": [{"id": 2}], "next": None}, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="cursor", cursor_param="cursor", cursor_path=("next",)
        ),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]


def test_cursor_next_url_path_follows_full_url(http_server):
    def route(query, headers, body):
        if query.get("p") == "2":
            return 200, {"data": [{"id": 2}]}, {}
        return 200, {"data": [{"id": 1}], "next_url": f"{http_server.url}/posts?p=2"}, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(type="cursor", next_url_path=("next_url",)),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/test_pagination_cursor.py -v`
Expected: FAIL (no cursor branch)

- [ ] **Step 3: Implement**

Add the `cursor` branch:
```jinja
{% elif pagination_type == "cursor" %}
def fetch_records():
    """Yield records, following the response cursor."""
    session = requests.Session()
    session.headers.update(HEADERS)
{% if next_url_path %}
    url, params = f"{BASE_URL}{PATH}", dict(PARAMS)
    while True:
        response = _request(session, url, params)
        payload = response.json()
        records = _records(payload)
        if records:
            yield from records
        next_url = _dig(payload, {{ next_url_path }})
        if not next_url:
            return
        url, params = next_url, None
{% else %}
    cursor = {{ initial_cursor | tojson }}
    while True:
        params = dict(PARAMS)
{% if limit_param and page_size %}
        params["{{ limit_param }}"] = {{ page_size }}
{% endif %}
        if cursor is not None:
            params["{{ cursor_param }}"] = cursor
        response = _request(session, f"{BASE_URL}{PATH}", params)
        payload = response.json()
        records = _records(payload)
        if records:
            yield from records
{% if cursor_header %}
        cursor = response.headers.get("{{ cursor_header }}")
{% else %}
        cursor = _dig(payload, {{ cursor_path }})
{% endif %}
        if not cursor:
            return
{% endif %}
{% endif %}
```
`_context`: `cursor_param=stream.pagination.cursor_param or "cursor"`, `cursor_path=list(...) or None`, `next_url_path=list(...) or None`, `cursor_header`, `initial_cursor`. Ensure `_dig` is emitted when any of these paths is set (extend the Task 5 condition).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): cursor pagination block"
```

---

### Task 7: Link-header pagination

**Files:**
- Modify: `generator.py`, `templates/core.py.jinja`
- Test: `tests/codegen/test_pagination_link_header.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from polymo.config import PaginationConfig
from tests.codegen.helpers import make_config, run_generated


def test_link_header_pagination(http_server):
    def route(query, headers, body):
        if query.get("p") == "2":
            return 200, [{"id": 2}], {}
        link = f'<{http_server.url}/posts?p=2>; rel="next"'
        return 200, [{"id": 1}], {"Link": link}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url, pagination=PaginationConfig(type="link_header")
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/codegen/test_pagination_link_header.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```jinja
{% elif pagination_type == "link_header" %}
def fetch_records():
    """Yield records, following RFC 5988 Link headers (rel=next)."""
    session = requests.Session()
    session.headers.update(HEADERS)
    url, params = f"{BASE_URL}{PATH}", dict(PARAMS)
    while url:
        response = _request(session, url, params)
        records = _records(response.json())
        if records:
            yield from records
        url, params = response.links.get("next", {}).get("url"), None
{% endif %}
```
(`requests` parses the Link header into `response.links` — no manual parsing.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): link-header pagination block"
```

---

### Task 8: Bearer auth block

**Files:**
- Modify: `generator.py`, `templates/core.py.jinja`
- Test: `tests/codegen/test_auth_bearer.py`

**Interfaces:**
- Produces: context key `auth_type`; bearer scripts start with an `API_TOKEN` variable + key-vault comment. `run_generated` callers can set `module`-level token by exec'ing with an override — add helper param `run_generated(config, override_globals=None)` that merges dict into the namespace between exec and return? No — token must apply before use, and fetch reads module global at call time, so merging after exec works: `ns.update(override_globals or {})` after exec, before returning.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from polymo.codegen import generate_core
from polymo.config import AuthConfig
from tests.codegen.helpers import make_config, run_generated


def test_bearer_placeholder_and_comment_present():
    config = make_config(base_url="https://x", auth=AuthConfig(type="bearer", token="s3cret"))
    core = generate_core(config)
    assert 'API_TOKEN = "REPLACE_ME"' in core
    assert "s3cret" not in core
    assert "dbutils.secrets.get" in core  # recommendation comment


def test_bearer_header_sent(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Bearer tok-123"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(base_url=http_server.url, auth=AuthConfig(type="bearer"))
    module = run_generated(config, override_globals={"API_TOKEN": "tok-123"})
    assert list(module.fetch_records()) == [{"id": 1}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/test_auth_bearer.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Extend `run_generated` in `helpers.py`:
```python
def run_generated(config, override_globals=None):
    code = generate_core(config)
    assert_hygiene(code)
    namespace: dict[str, Any] = {}
    exec(compile(code, "<generated>", "exec"), namespace)  # noqa: S102
    namespace.update(override_globals or {})
    return SimpleNamespace(**namespace)
```
Wait — `SimpleNamespace` copies, so functions captured their own module globals dict; updating `namespace` (the exec globals) BEFORE wrapping works because functions reference that same dict. Keep the update before `SimpleNamespace(...)` as shown.

Template, after `TIMEOUT`:
```jinja
{% if auth_type == "bearer" %}

# Fill in your token. For anything beyond local testing, fetch it from a
# secret store instead of keeping it in this file, e.g.:
#   API_TOKEN = dbutils.secrets.get("my-scope", "my-key")
# or an Azure Key Vault / AWS Secrets Manager client.
API_TOKEN = "REPLACE_ME"
{% endif %}
```
And in every `fetch_records` branch, directly after `session.headers.update(HEADERS)`:
```jinja
{% if auth_type in ("bearer", "oauth2") %}
    session.headers["Authorization"] = f"Bearer {API_TOKEN}"
{% endif %}
```
(Task 9 redefines `API_TOKEN` for oauth2 via `get_token()`.) Context: `auth_type=config.auth.type`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): bearer auth block with secret-store guidance"
```

---

### Task 9: OAuth2 client-credentials block

**Files:**
- Modify: `generator.py`, `templates/core.py.jinja`
- Test: `tests/codegen/test_auth_oauth2.py`

**Interfaces:**
- Produces: generated `get_token() -> str` (form-encoded POST to token_url; client_id/client_secret/scope/audience/extra inlined; `CLIENT_SECRET = "REPLACE_ME"` placeholder); `API_TOKEN = get_token()`.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from urllib.parse import parse_qs

from polymo.config import AuthConfig
from tests.codegen.helpers import make_config, run_generated


def test_oauth2_token_fetched_and_used(http_server):
    def token_route(query, headers, body):
        form = {k: v[-1] for k, v in parse_qs(body.decode()).items()}
        assert form["grant_type"] == "client_credentials"
        assert form["client_id"] == "cid"
        assert form["client_secret"] == "sec"
        assert form["scope"] == "read write"
        return 200, {"access_token": "tok-oauth"}, {}

    def data_route(query, headers, body):
        assert headers.get("Authorization") == "Bearer tok-oauth"
        return 200, [{"id": 1}], {}

    http_server.routes["/oauth/token"] = token_route
    http_server.routes["/posts"] = data_route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(
            type="oauth2",
            token_url=f"{http_server.url}/oauth/token",
            client_id="cid",
            scope=("read", "write"),
        ),
    )
    module = run_generated(config, override_globals={"CLIENT_SECRET": "sec"})
    assert list(module.fetch_records()) == [{"id": 1}]
```

Note: `API_TOKEN = get_token()` at import time would fetch before the override lands. Therefore the template must fetch lazily — assert also:
```python
def test_oauth2_lazy_token(http_server):
    # generation itself must not require a live token endpoint
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="oauth2", token_url="https://x/token", client_id="cid"),
    )
    from polymo.codegen import generate_core
    assert "def get_token" in generate_core(config)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/test_auth_oauth2.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Template block (replaces the bearer block when `auth_type == "oauth2"`):
```jinja
{% if auth_type == "oauth2" %}

# Fill in your client secret. For anything beyond local testing, fetch it
# from a secret store instead of keeping it in this file, e.g.:
#   CLIENT_SECRET = dbutils.secrets.get("my-scope", "my-key")
CLIENT_SECRET = "REPLACE_ME"
TOKEN_URL = "{{ token_url }}"


def get_token():
    """Fetch an OAuth2 access token (client credentials grant)."""
    payload = {
        "grant_type": "client_credentials",
        "client_id": "{{ client_id }}",
        "client_secret": CLIENT_SECRET,
{% if scope %}
        "scope": "{{ scope }}",
{% endif %}
{% if audience %}
        "audience": "{{ audience }}",
{% endif %}
{% for key, value in oauth_extra.items() %}
        "{{ key }}": {{ value | tojson }},
{% endfor %}
    }
    response = requests.post(TOKEN_URL, data=payload, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["access_token"]
{% endif %}
```
And the auth line in fetch branches becomes, for oauth2:
```jinja
{% if auth_type == "oauth2" %}
    session.headers["Authorization"] = f"Bearer {get_token()}"
{% elif auth_type == "bearer" %}
    session.headers["Authorization"] = f"Bearer {API_TOKEN}"
{% endif %}
```
Context: `token_url`, `client_id`, `scope=" ".join(auth.scope)`, `audience`, `oauth_extra=dict(auth.extra_params)`. Raise `CodegenError("oauth2 requires token_url and client_id")` if either is missing.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): oauth2 client-credentials block"
```

---

### Task 10: Generation-time templating + schema emission

**Files:**
- Modify: `generator.py`, `templates/core.py.jinja`, `templates/dp.py.jinja`
- Test: `tests/codegen/test_templating_and_schema.py`

**Interfaces:**
- Consumes: polymo's existing runtime rendering (`polymo.rest_client._render_template`) — reused at *generation* time so `{{ options.x }}` in params/headers/path resolves to literals in the output.
- Produces: context keys `schema_ddl` (str|None); dp wiring emits `SCHEMA = "<ddl>"` and passes `schema=SCHEMA`.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from polymo.codegen import generate, generate_core
from tests.codegen.helpers import assert_hygiene, make_config


def test_params_templates_resolved_at_generation_time():
    config = make_config(
        base_url="https://x",
        params={"country": "{{ options.country }}"},
        options={"country": "NL"},
    )
    core = generate_core(config)
    assert '"country": "NL"' in core
    assert "{{" not in core


def test_schema_ddl_emitted_in_dp_wiring():
    config = make_config(base_url="https://x", schema="id BIGINT, name STRING")
    script = generate(config)
    assert_hygiene(script)
    assert 'SCHEMA = "id BIGINT, name STRING"' in script
    assert "schema=SCHEMA" in script


def test_no_schema_falls_back_to_inference():
    config = make_config(base_url="https://x")
    script = generate(config)
    assert "SCHEMA" not in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/test_templating_and_schema.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

In `_context`, before building reprs, resolve templates with the same context shape the runtime uses (`options`, `params`, `headers`, `raw_params`):
```python
from ..rest_client import _render_template

def _resolved(stream, options):
    ctx = {
        "options": dict(options or {}),
        "params": dict(stream.params or {}),
        "headers": dict(stream.headers or {}),
        "raw_params": dict(stream.params or {}),
    }
    params = {k: _render_template(v, ctx) for k, v in (stream.params or {}).items()}
    ctx["params"] = params
    headers = {k: _render_template(v, ctx) for k, v in (stream.headers or {}).items()}
    path = _render_template(stream.path, ctx)
    return params, headers, path
```
Use its results for `params_repr`, `headers_repr`, `path`. (When Phase 3 deletes `rest_client.py`, `_render_template` and its two helpers move into `codegen/` — noted in the Phase 3 plan.)

Context: `schema_ddl=stream.schema` (already a DDL string or None). `dp.py.jinja` becomes:
```jinja
from pyspark import pipelines as dp
from pyspark.sql import SparkSession

spark = SparkSession.getActiveSession()

{% if schema_ddl %}
SCHEMA = {{ schema_ddl | tojson }}
{% endif %}


@dp.table(name="{{ stream_name }}")
def {{ func_name }}():
{% if schema_ddl %}
    return spark.createDataFrame(list(fetch_records()), schema=SCHEMA)
{% else %}
    return spark.createDataFrame(list(fetch_records()))
{% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): generation-time templating and DDL schema emission"
```

---

### Task 11: Incremental state block (JSON file)

**Files:**
- Modify: `generator.py`, `templates/core.py.jinja`, `templates/dp.py.jinja`
- Test: `tests/codegen/test_incremental.py`

**Interfaces:**
- Produces: generated `STATE_PATH`, `_read_state() -> dict`, `_write_state(cursor)`; `fetch_records` applies `cursor_param` from state and tracks `max(cursor_field)`; the dp table function persists state after materializing.

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

import json

from polymo.config import IncrementalConfig
from tests.codegen.helpers import make_config, run_generated


def test_incremental_reads_and_writes_state(http_server, tmp_path):
    state_file = tmp_path / "state.json"

    def route(query, headers, body):
        since = query.get("since")
        if since is None:
            return 200, [{"id": 1, "updated": "2026-01-01"}], {}
        assert since == "2026-01-01"
        return 200, [{"id": 2, "updated": "2026-02-01"}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
    )
    module = run_generated(config, override_globals={"STATE_PATH": str(state_file)})

    records = list(module.fetch_records())
    module._write_state(module.LAST_CURSOR["value"])
    assert json.loads(state_file.read_text()) == {"cursor": "2026-01-01"}

    module2 = run_generated(config, override_globals={"STATE_PATH": str(state_file)})
    assert list(module2.fetch_records()) == [{"id": 2, "updated": "2026-02-01"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/codegen/test_incremental.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Template additions when `incremental_mode` is truthy (context: `incremental_mode`, `cursor_param_inc=stream.incremental.cursor_param`, `cursor_field=stream.incremental.cursor_field`), placed after config constants:
```jinja
{% if incremental_mode %}
import json
import os

# Where the incremental cursor is stored between runs. Point this at a
# durable path (e.g. a Databricks Volume: /Volumes/cat/schema/vol/{{ stream_name }}.json).
STATE_PATH = "{{ stream_name }}_state.json"
LAST_CURSOR = {"value": None}


def _read_state():
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH) as fh:
        return json.load(fh)


def _write_state(cursor):
    if cursor is None:
        return
    with open(STATE_PATH, "w") as fh:
        json.dump({"cursor": cursor}, fh)
{% endif %}
```
In every `fetch_records` branch: after building `params = dict(PARAMS)` (the `none` branch switches to the same `params = dict(PARAMS)` shape), add:
```jinja
{% if incremental_mode %}
        cursor = _read_state().get("cursor")
        if cursor is not None:
            params["{{ cursor_param_inc }}"] = cursor
{% endif %}
```
(for the `none` branch, unindented one level) and after `yield from records`:
```jinja
{% if incremental_mode %}
        for record in records:
            value = record.get("{{ cursor_field }}")
            if value is not None and (LAST_CURSOR["value"] is None or value > LAST_CURSOR["value"]):
                LAST_CURSOR["value"] = value
{% endif %}
```
Note: read state ONCE before the loop (hoist the `_read_state()` call above `while True:` — a cursor page-walk must not re-read state per page).

`dp.py.jinja` table function persists after materializing:
```jinja
@dp.table(name="{{ stream_name }}")
def {{ func_name }}():
    rows = list(fetch_records())
{% if incremental_mode %}
    _write_state(LAST_CURSOR["value"])
{% endif %}
{% if schema_ddl %}
    return spark.createDataFrame(rows, schema=SCHEMA)
{% else %}
    return spark.createDataFrame(rows)
{% endif %}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): incremental cursor state via JSON file"
```

---

### Task 12: Partition windows (param_range / values / endpoints / pagination)

**Files:**
- Modify: `generator.py`, `templates/core.py.jinja`, `templates/dp.py.jinja`; `src/polymo/config.py` (add `streaming: bool = False` to `StreamConfig` — used by Task 13, added here so goldens stay stable)
- Test: `tests/codegen/test_partitions.py`

**Interfaces:**
- Consumes: window-planning logic mirrored from `_plan_partitions` in `src/polymo/datasource.py:364` — read it before implementing; the generator expands windows to a literal `WINDOWS` list at generation time using a new `_static_windows(config) -> list[dict] | None` (None = pagination strategy / not statically knowable).
- Produces: `fetch_records(extra_params=None, path=None)` signature on every branch; generated `WINDOWS` literal; dp wiring parallelizes via `spark.sparkContext.parallelize`.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from polymo.config import PartitionConfig
from tests.codegen.helpers import make_config, run_generated


def test_param_range_numeric_windows_inlined(http_server):
    seen = []

    def route(query, headers, body):
        seen.append(query.get("region"))
        return 200, [{"region": query.get("region")}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        partition=PartitionConfig(
            strategy="param_range", param="region", range_start=1, range_end=3,
            range_step=1, range_kind="numeric",
        ),
    )
    module = run_generated(config)
    assert module.WINDOWS == [
        {"extra_params": {"region": "1"}},
        {"extra_params": {"region": "2"}},
        {"extra_params": {"region": "3"}},
    ]
    records = [r for w in module.WINDOWS for r in module.fetch_records(**w)]
    assert sorted(seen) == ["1", "2", "3"]


def test_endpoints_windows(http_server):
    http_server.routes["/a"] = lambda q, h, b: (200, [{"src": "a"}], {})
    http_server.routes["/b"] = lambda q, h, b: (200, [{"src": "b"}], {})
    config = make_config(
        base_url=http_server.url,
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
    )
    module = run_generated(config)
    records = [r for w in module.WINDOWS for r in module.fetch_records(**w)]
    assert records == [{"src": "a"}, {"src": "b"}]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/test_partitions.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

`_static_windows(config)` in `generator.py` — mirror `_plan_param_range_partitions` / `_plan_endpoint_partitions` semantics by reading `src/polymo/datasource.py` (values list, numeric and date ranges with `range_step`, `value_template`/`extra_template` rendered per value, endpoint list). Date ranges iterate `datetime.date.fromisoformat(start)` to end by `timedelta(days=range_step or 1)`. Return e.g. `[{"extra_params": {...}}, ...]` or `[{"path": "/a"}, ...]`; `None` for `strategy in ("none", "pagination")`. Values are stringified like the runtime does.

Every `fetch_records` branch gets the signature `def fetch_records(extra_params=None, path=None):` and uses:
```jinja
    url_path = path or PATH
```
… `f"{BASE_URL}{url_path}"` replaces `f"{BASE_URL}{PATH}"`, and after `params = dict(PARAMS)`:
```jinja
        if extra_params:
            params.update(extra_params)
```
Emit after the config constants, only when windows exist:
```jinja
{% if windows_repr %}
# One entry per partition; each is fetched independently (parallelized
# across executors in the dp table below).
WINDOWS = {{ windows_repr }}
{% endif %}
```
dp wiring when windows exist:
```jinja
@dp.table(name="{{ stream_name }}")
def {{ func_name }}():
    sc = spark.sparkContext
    rows = sc.parallelize(WINDOWS, len(WINDOWS)).flatMap(
        lambda window: list(fetch_records(**window))
    ).collect()
{% if incremental_mode %}
    _write_state(LAST_CURSOR["value"])
{% endif %}
{% if schema_ddl %}
    return spark.createDataFrame(rows, schema=SCHEMA)
{% else %}
    return spark.createDataFrame(rows)
{% endif %}
```
For `strategy == "pagination"` emit the plain sequential table function (pagination already walks all pages) — document with a comment line in the script: `# partition strategy "pagination" runs sequentially in generated scripts`.

Add `streaming: bool = False` to `StreamConfig` in `src/polymo/config.py` (no other config change).

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/ -v`  (full suite — config change touches runtime tests)
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): static partition windows with parallel dp wiring"
```

---

### Task 13: Streaming variant (inline Spark DataSource)

**Files:**
- Modify: `generator.py`, `templates/dp.py.jinja` (new `{% if streaming %}` branch)
- Test: `tests/codegen/test_streaming.py`

**Interfaces:**
- Consumes: `StreamConfig.streaming` flag (Task 12); generated `fetch_records` core unchanged.
- Produces: streaming scripts embed a `RestStreamSource(DataSource)` + `SimpleDataSourceStreamReader` pair, register it, and define the table with `spark.readStream`. Requires `schema_ddl` and pagination type `offset` or `page` — otherwise `CodegenError`.

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import ast

import pytest

from polymo.codegen import CodegenError, generate
from polymo.config import PaginationConfig
from tests.codegen.helpers import make_config


def test_streaming_requires_schema_and_offset_or_page():
    config = make_config(base_url="https://x", streaming=True)
    with pytest.raises(CodegenError):
        generate(config)


def test_streaming_script_structure():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    script = generate(config)
    ast.parse(script)
    assert "class RestStreamSource" in script
    assert "SimpleDataSourceStreamReader" in script
    assert "spark.dataSource.register(RestStreamSource)" in script
    assert "spark.readStream" in script
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/codegen/test_streaming.py -v`
Expected: FAIL

- [ ] **Step 3: Implement**

`generate()` raises `CodegenError` when `stream.streaming` and (`not stream.schema` or `stream.pagination.type not in ("offset", "page")`). The core template additionally emits (streaming only) a single-page fetch built from the same building blocks:
```jinja
{% if streaming %}


def fetch_page(page_index):
    """Fetch one page by index; returns a list of records."""
    session = requests.Session()
    session.headers.update(HEADERS)
{% if auth_type == "oauth2" %}
    session.headers["Authorization"] = f"Bearer {get_token()}"
{% elif auth_type == "bearer" %}
    session.headers["Authorization"] = f"Bearer {API_TOKEN}"
{% endif %}
    params = dict(PARAMS)
{% if limit_param and page_size %}
    params["{{ limit_param }}"] = {{ page_size }}
{% endif %}
{% if pagination_type == "page" %}
    params["{{ page_param }}"] = {{ start_page }} + page_index
{% else %}
    params["{{ offset_param }}"] = {{ start_offset }} + page_index * {{ page_size }}
{% endif %}
    response = _request(session, f"{BASE_URL}{PATH}", params)
    return _records(response.json())
{% endif %}
```
`dp.py.jinja` streaming branch (replaces the batch `@dp.table`):
```jinja
{% if streaming %}
from pyspark.sql.datasource import DataSource, SimpleDataSourceStreamReader

COLUMNS = [f.split()[0] for f in SCHEMA.split(",")]


class _Reader(SimpleDataSourceStreamReader):
    def initialOffset(self):
        return {"page": 0}

    def read(self, start):
        page = start["page"]
        records = fetch_page(page)
        rows = [tuple(r.get(c) for c in COLUMNS) for r in records]
        next_page = page + 1 if records else page
        return iter(rows), {"page": next_page}


class RestStreamSource(DataSource):
    @classmethod
    def name(cls):
        return "{{ func_name }}_stream"

    def schema(self):
        return SCHEMA

    def simpleStreamReader(self, schema):
        return _Reader()


spark.dataSource.register(RestStreamSource)


@dp.table(name="{{ stream_name }}")
def {{ func_name }}():
    return spark.readStream.format("{{ func_name }}_stream").load()
{% else %}
... existing batch @dp.table branch ...
{% endif %}
```
(`SCHEMA` emission from Task 10 is required, guaranteed by the CodegenError guard. `COLUMNS` derives names from the DDL — a comment in the template notes it assumes simple `name TYPE` pairs.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/codegen/ -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(codegen): streaming variant with inline Spark DataSource"
```

---

### Task 14: Golden files + full-matrix hygiene sweep

**Files:**
- Create: `tests/codegen/test_golden.py`, `tests/codegen/golden/` (generated by the test on first run)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the test (self-seeding goldens)**

```python
from __future__ import annotations

from pathlib import Path

import pytest

from polymo.codegen import generate
from polymo.config import (
    AuthConfig, IncrementalConfig, PaginationConfig, PartitionConfig,
    RecordSelectorConfig,
)
from tests.codegen.helpers import assert_hygiene, make_config

GOLDEN_DIR = Path(__file__).parent / "golden"

CASES = {
    "rdw_offset": make_config(
        base_url="https://opendata.rdw.nl",
        name="gekentekende_voertuigen",
        path="/resource/m9d7-ebf2.json",
        params={"$order": "kenteken"},
        pagination=PaginationConfig(
            type="offset", page_size=1000, limit_param="$limit", offset_param="$offset"
        ),
    ),
    "bearer_cursor_selector": make_config(
        base_url="https://api.example.com",
        auth=AuthConfig(type="bearer"),
        pagination=PaginationConfig(type="cursor", cursor_param="after", cursor_path=("meta", "next")),
        record_selector=RecordSelectorConfig(field_path=["data"]),
    ),
    "oauth_incremental_partitioned": make_config(
        base_url="https://api.example.com",
        auth=AuthConfig(type="oauth2", token_url="https://api.example.com/token", client_id="cid"),
        incremental=IncrementalConfig(mode="cursor", cursor_param="since", cursor_field="updated"),
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
        schema="id BIGINT, updated STRING",
    ),
    "streaming_page": make_config(
        base_url="https://api.example.com",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    ),
}


@pytest.mark.parametrize("case", CASES)
def test_golden(case):
    script = generate(CASES[case])
    assert_hygiene(script)
    golden = GOLDEN_DIR / f"{case}.py"
    if not golden.exists():
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden.write_text(script)
        pytest.skip(f"golden seeded: {golden}")
    assert script == golden.read_text(), (
        f"generated output changed; if intended, delete {golden} and rerun"
    )
```

- [ ] **Step 2: Run twice**

Run: `.venv/bin/python -m pytest tests/codegen/test_golden.py -v` (seeds, skips)
Run again: Expected: 4 PASS

- [ ] **Step 3: Read every golden file end-to-end**

Open each file in `tests/codegen/golden/` and read it as a user would. This is the KISS gate: if any script has dead code, unused helpers, or confusing structure for its config, fix the template and reseed. Specifically check: no `_dig` when unused, no `import time`/`json`/`os` when unused, docstrings match the chosen options.

- [ ] **Step 4: Run full suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "test(codegen): golden scripts for representative configs"
```

---

### Task 15: Export from package + phase wrap-up

**Files:**
- Modify: `src/polymo/__init__.py` (add `generate` to exports), `README.md` (one short "What's coming in 1.0" note linking the spec)

- [ ] **Step 1: Write the failing test** — extend `tests/codegen/test_baseline.py`:

```python
def test_generate_exported_from_package():
    from polymo import generate as top_level_generate
    from polymo.codegen import generate
    assert top_level_generate is generate
```

- [ ] **Step 2: Run to verify it fails**, **Step 3: add the export + README note**, **Step 4: full suite green**, **Step 5: Commit:**

```bash
git add -A && git commit -m "feat(codegen): export generate; announce 1.0 direction"
```

---

## Self-Review Notes

- Spec coverage: pagination ×5 (Tasks 1,4,5,6,7), bearer/oauth2 (8,9), retries (3), record selector (2), templating + schema (10), incremental (11), partitions (12), streaming (13), goldens/hygiene (14), zero-polymo-imports guard (Task 1 test). Builder rewire and deletions are Phase 2/3 plans, per scope check.
- `cast_to_schema_types`: covered via explicit DDL schema in `createDataFrame` (Spark casts on ingest) — intentional simplification, noted in Task 2.
- Type consistency: `fetch_records(extra_params=None, path=None)` established in Task 12 changes earlier branches — Task 12 explicitly owns that signature migration and reseeding goldens happens in Task 14 (which runs after).
