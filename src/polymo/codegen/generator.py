"""Render standalone Lakeflow Declarative Pipelines scripts from a config."""

from __future__ import annotations

import ast as _ast
import json
import re
from typing import Any, Dict

from jinja2 import Environment, PackageLoader, StrictUndefined

from ..config import RestSourceConfig
from ..rest_client import _render_template


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


def _retry_condition(retry_statuses) -> str:
    checks = []
    for spec in retry_statuses:
        if spec.endswith("XX"):
            base = int(spec[0]) * 100
            checks.append(f"{base} <= status <= {base + 99}")
        else:
            checks.append(f"status == {int(spec)}")
    return " or ".join(checks) or "False"


def _py_literal(value: Any) -> str:
    """Render a value as a Python literal, using double-quoted strings.

    Behaves like `repr()` except string values (including dict keys) are
    quoted with `json.dumps` so generated output uses double quotes, matching
    the rest of the generated source's quoting style.
    """
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, dict):
        items = ", ".join(
            f"{_py_literal(k)}: {_py_literal(v)}" for k, v in value.items()
        )
        return "{" + items + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_py_literal(v) for v in value) + "]"
    return repr(value)


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


def _context(config: RestSourceConfig) -> Dict[str, Any]:
    stream = config.stream
    eh = stream.error_handler
    auth = config.auth
    if auth.type == "oauth2" and (not auth.token_url or not auth.client_id):
        raise CodegenError("oauth2 requires token_url and client_id")
    params, headers, path = _resolved(stream, config.options)
    return {
        "auth_type": auth.type,
        "token_url": auth.token_url,
        "client_id": auth.client_id,
        "scope": " ".join(auth.scope),
        "audience": auth.audience,
        "oauth_extra_items": [(k, repr(v)) for k, v in auth.extra_params.items()],
        "base_url": config.base_url.rstrip("/"),
        "path": path,
        "params_repr": _py_literal(params),
        "headers_repr": _py_literal(headers),
        "schema_ddl": stream.schema,
        "stream_name": stream.name,
        "func_name": _identifier(stream.name),
        "field_path": list(stream.record_selector.field_path) or None,
        "record_filter_expr": _filter_expression(stream.record_selector.record_filter),
        "max_retries": eh.max_retries,
        "retry_condition": _retry_condition(eh.retry_statuses),
        "initial_delay": eh.backoff.initial_delay_seconds,
        "max_delay": eh.backoff.max_delay_seconds,
        "multiplier": eh.backoff.multiplier,
        "retry_on_timeout": eh.retry_on_timeout,
        "retry_on_connection_errors": eh.retry_on_connection_errors,
        "pagination_type": stream.pagination.type,
        "page_size": stream.pagination.page_size,
        "limit_param": stream.pagination.limit_param,
        "offset_param": stream.pagination.offset_param or "offset",
        "start_offset": stream.pagination.start_offset,
        "stop_on_empty": stream.pagination.stop_on_empty_response,
        "page_param": stream.pagination.page_param or "page",
        "start_page": stream.pagination.start_page,
        "total_pages_path": list(stream.pagination.total_pages_path) or None,
        "total_pages_header": stream.pagination.total_pages_header,
        "cursor_param": stream.pagination.cursor_param or "cursor",
        "cursor_path": list(stream.pagination.cursor_path) or None,
        "cursor_header": stream.pagination.cursor_header,
        "next_url_path": list(stream.pagination.next_url_path) or None,
        "initial_cursor_repr": repr(stream.pagination.initial_cursor),
    }


def generate_core(config: RestSourceConfig) -> str:
    return _ENV.get_template("core.py.jinja").render(**_context(config))


def generate(config: RestSourceConfig) -> str:
    core = generate_core(config)
    dp_wiring = _ENV.get_template("dp.py.jinja").render(**_context(config))
    return core + "\n\n" + dp_wiring
