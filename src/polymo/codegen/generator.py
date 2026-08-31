"""Render standalone Lakeflow Declarative Pipelines scripts from a config."""

from __future__ import annotations

import ast as _ast
import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional

from jinja2 import Environment, PackageLoader, StrictUndefined

from ..config import PartitionConfig, RestSourceConfig
from .templating import _PathFormatter, _render_template


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


_OPTION_REF_RE = re.compile(
    r'\{\{\s*options(?:\.([A-Za-z_]\w*)|\[["\']([^"\']+)["\']\])\s*\}\}'
)

# Markers are wrapped in NUL bytes so they can never collide with anything a
# real config value could legitimately contain, yet are trivial to find
# again in a rendered string via `_MARKER_RE`.
_MARKER_RE = re.compile(r"\x00(OPT_[A-Za-z0-9_]*)\x00")


def _option_placeholder_var(name: str) -> str:
    """Turn an unresolved option name into a `OPT_<NAME>` Python identifier."""
    cleaned = re.sub(r"\W", "_", name).upper()
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"_{cleaned}"
    return f"OPT_{cleaned}"


def _scan_option_refs(*texts: Optional[str]) -> Dict[str, str]:
    """Find every `{{ options.name }}` / `{{ options["name"] }}` reference.

    Returns an ordered (first-seen) mapping of option name -> the
    placeholder variable name it would get if left unresolved. Scanning the
    raw template strings directly (before Jinja ever sees them) means this
    works even for options that ARE present in `config.options` — the
    caller decides which of the returned names are actually missing.
    """
    found: Dict[str, str] = {}
    for text in texts:
        if not isinstance(text, str) or "options" not in text:
            continue
        for match in _OPTION_REF_RE.finditer(text):
            name = match.group(1) or match.group(2)
            if name not in found:
                found[name] = _option_placeholder_var(name)
    return found


def _fstring_escape(text: str) -> str:
    """Escape literal text for safe inclusion inside an `f"..."` literal.

    `json.dumps` handles backslashes/quotes/control characters the same way
    a double-quoted Python string literal needs them escaped; stripping its
    surrounding quotes leaves just the escaped body. On top of that, any
    literal `{`/`}` must be doubled so an f-string doesn't mistake it for an
    interpolation delimiter.
    """
    body = json.dumps(text)[1:-1]
    return body.replace("{", "{{").replace("}", "}}")


def _fstring_literal(value: str) -> str:
    """Render a string containing `\\x00OPT_*\\x00` markers as an f-string.

    Marker segments become `{VAR}` interpolations referencing the
    placeholder variable; everything else is escaped via `_fstring_escape`.
    """
    parts: List[str] = []
    last = 0
    for match in _MARKER_RE.finditer(value):
        parts.append(_fstring_escape(value[last : match.start()]))
        parts.append("{" + match.group(1) + "}")
        last = match.end()
    parts.append(_fstring_escape(value[last:]))
    return 'f"' + "".join(parts) + '"'


def _py_literal(value: Any) -> str:
    """Render a value as a Python literal, using double-quoted strings.

    Behaves like `repr()` except string values (including dict keys) are
    quoted with `json.dumps` so generated output uses double quotes, matching
    the rest of the generated source's quoting style. A string carrying
    `\\x00OPT_*\\x00` markers (an unresolved `{{ options.* }}` reference,
    see `_resolved`) is instead rendered as an f-string that interpolates
    the corresponding `OPT_*` placeholder variable at request time.
    """
    if isinstance(value, str):
        if _MARKER_RE.search(value):
            return _fstring_literal(value)
        return json.dumps(value)
    if isinstance(value, dict):
        items = ", ".join(
            f"{_py_literal(k)}: {_py_literal(v)}" for k, v in value.items()
        )
        return "{" + items + "}"
    if isinstance(value, list):
        return "[" + ", ".join(_py_literal(v) for v in value) + "]"
    return repr(value)


def _comment_escape(value: str) -> str:
    """Make a value safe to interpolate into a `#`-style comment.

    A `#` comment runs to the end of its physical line, so an embedded
    newline in the value would let text after it land on its own line as
    live Python instead of comment text. Collapsing newlines to spaces
    keeps the whole value on one comment line no matter what it contains.
    """
    return " ".join(value.splitlines())


def _doc_escape(value: str) -> str:
    """Escape a value for safe interpolation inside a triple-double-quoted docstring.

    Escaping backslashes and every double quote guarantees the content can
    never contain an unescaped run of three double quotes (or a trailing
    backslash that would swallow the closing delimiter), so it can't break
    out of the docstring no matter what the source config value contains.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _parse_partition_values(raw: Any) -> List[str]:
    """Parse a partition `values` config entry into a list of strings."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        return [str(item) for item in raw]

    text = str(raw).strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return [chunk.strip() for chunk in text.split(",") if chunk.strip()]

    if isinstance(parsed, list):
        return [str(item) for item in parsed]
    if isinstance(parsed, (str, int, float)):
        return [str(parsed)]
    return []


def _generate_range_values(partition: PartitionConfig) -> List[str]:
    """Generate a list of partition values from a range config."""
    start_raw = partition.range_start
    end_raw = partition.range_end
    if start_raw is None or end_raw is None:
        return []

    kind = partition.range_kind or "numeric"
    step_raw = partition.range_step

    if kind in {"numeric", "number", "int", "integer"} or kind is None:
        try:
            start = int(str(start_raw))
            end = int(str(end_raw))
            step = int(str(step_raw)) if step_raw is not None else 1
        except (ValueError, TypeError) as exc:
            raise CodegenError(
                "Range values must be valid integers for numeric ranges"
            ) from exc

        if step <= 0:
            raise CodegenError("range_step must be greater than 0 for numeric ranges")

        values: List[str] = []
        if start <= end:
            current = start
            while current <= end:
                values.append(str(current))
                current += step
        else:
            current = start
            while current >= end:
                values.append(str(current))
                current -= step
        return values

    if kind == "date":
        try:
            start_date = datetime.fromisoformat(str(start_raw)).date()
            end_date = datetime.fromisoformat(str(end_raw)).date()
            step_days = int(str(step_raw)) if step_raw is not None else 1
        except (ValueError, TypeError) as exc:
            raise CodegenError(
                "Range values must be valid ISO dates for date ranges"
            ) from exc

        if step_days <= 0:
            raise CodegenError("range_step must be greater than 0 for date ranges")

        delta = timedelta(days=step_days)
        values = []
        if start_date <= end_date:
            current = start_date
            while current <= end_date:
                values.append(current.isoformat())
                current += delta
        else:
            current = start_date
            while current >= end_date:
                values.append(current.isoformat())
                current -= delta
        return values

    raise CodegenError(
        "range_kind must be 'numeric' or 'date' when using partition_strategy='param_range'"
    )


def _apply_value_template(value: str, template: Optional[str]) -> str:
    if not template:
        return value
    return template.replace("{{value}}", value)


def _render_extra_params(template: str, value: str) -> Dict[str, Any]:
    rendered = template.replace("{{value}}", value)
    try:
        payload = json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise CodegenError("partition_extra_template must be valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise CodegenError("partition_extra_template must resolve to a JSON object")
    return {str(key): str(payload[key]) for key in payload}


def _static_param_range_windows(partition: PartitionConfig) -> List[Dict[str, Any]]:
    """Expand a `param_range` partition strategy into literal windows."""
    if not partition.param:
        raise CodegenError(
            "partition_strategy='param_range' requires 'param' to be set"
        )
    param = partition.param

    values = _parse_partition_values(partition.values)
    if not values:
        values = _generate_range_values(partition)

    if not values:
        raise CodegenError(
            "partition_strategy='param_range' requires either 'values' or range configuration"
        )

    template_str = partition.value_template
    extra_template_str = partition.extra_template

    windows: List[Dict[str, Any]] = []
    for value in values:
        formatted = _apply_value_template(value, template_str)
        extra_params: Dict[str, Any] = {param: formatted}
        if extra_template_str:
            extra_params.update(_render_extra_params(extra_template_str, formatted))
        windows.append({"extra_params": extra_params})

    return windows


def _static_endpoint_windows(partition: PartitionConfig) -> List[Dict[str, Any]]:
    """Expand an `endpoints` partition strategy into literal windows."""
    if not partition.endpoints:
        raise CodegenError(
            "partition_strategy='endpoints' requires 'endpoints' to be defined"
        )

    windows: List[Dict[str, Any]] = []
    for endpoint in partition.endpoints:
        if ":" in endpoint:
            _, path = endpoint.split(":", 1)
            windows.append({"path": path.strip()})
        else:
            windows.append({"path": endpoint})

    return windows


def _static_windows(config: RestSourceConfig) -> Optional[List[Dict[str, Any]]]:
    """Expand the partition config into a literal WINDOWS list at generation time.

    Returns `None` when windows cannot be known statically: strategy "none"
    (no partitioning) or "pagination" (windows depend on a live probe of the
    API, so they can't be pre-computed at generation time).
    """
    partition = config.stream.partition
    strategy = partition.strategy if partition else "none"

    if strategy == "param_range":
        return _static_param_range_windows(partition)
    if strategy == "endpoints":
        return _static_endpoint_windows(partition)
    return None


def _resolved(stream, options):
    """Resolve templates and curly-brace path placeholders at generation time.

    Mirrors `RestClient.fetch_pages` (rest_client.py) exactly, so a placeholder
    like `/users/{user_id}/posts` with `params={"user_id": "42"}` substitutes
    `user_id` into the path and drops it from the emitted params, instead of
    leaving a literal `{user_id}` in PATH and a duplicate in PARAMS.

    A `{{ options.<name> }}` reference whose `<name>` is NOT present in
    `options` would normally blow up Jinja's `StrictUndefined` at render
    time (`/api/generate` passes no options at all, so this is the common
    case for any config that references options — e.g. the builder's
    api_key auth, or a hand-written `Authorization: Basic
    {{ options.api_key_b64 }}` header). Instead of failing, each missing
    name gets a unique marker substituted in as its "value" before
    rendering, so the template renders successfully; `_py_literal` (used to
    build PARAMS/HEADERS/PATH literals) then turns any string carrying a
    marker into an f-string that reads a `OPT_<NAME>` placeholder variable
    at request time (declared by the core template, defaulting to
    `"REPLACE_ME"`). Options that ARE present keep resolving inline exactly
    as before.
    """
    raw_options = dict(options or {})
    raw_texts = [stream.path]
    raw_texts.extend((stream.params or {}).values())
    raw_texts.extend((stream.headers or {}).values())
    referenced = _scan_option_refs(*raw_texts)
    missing = {name: var for name, var in referenced.items() if name not in raw_options}

    render_options = dict(raw_options)
    for name, var in missing.items():
        render_options[name] = f"\x00{var}\x00"

    ctx = {
        "options": render_options,
        "params": dict(stream.params or {}),
        "headers": dict(stream.headers or {}),
        "raw_params": dict(stream.params or {}),
    }
    rendered_params = {
        k: _render_template(v, ctx) for k, v in (stream.params or {}).items()
    }
    ctx["params"] = rendered_params

    formatter = _PathFormatter(rendered_params)
    rendered_path = _render_template(stream.path, ctx)
    path = formatter.render(rendered_path)

    params = {
        k: _render_template(v, ctx) for k, v in formatter.remaining_params().items()
    }
    headers = {k: _render_template(v, ctx) for k, v in (stream.headers or {}).items()}
    option_placeholders = list(dict.fromkeys(missing.values()))
    return params, headers, path, option_placeholders


def _require_no_xml_json_paths(stream) -> None:
    """XML responses can't be walked with the JSON-path digging helpers.

    These pagination/selector features all read a decoded JSON payload
    (`_dig`, or the record_selector's `field_path` walk); none of them make
    sense against an `xml.etree.ElementTree` element, so combining any of
    them with `response_format: xml` is rejected at generation time (which
    also guards the builder preview, since it calls `generate_core` too).
    """
    if stream.response_format != "xml":
        return
    incompatible = (
        ("cursor_path", stream.pagination.cursor_path),
        ("next_url_path", stream.pagination.next_url_path),
        ("total_pages_path", stream.pagination.total_pages_path),
        ("total_records_path", stream.pagination.total_records_path),
        ("record_selector.field_path", stream.record_selector.field_path),
    )
    for feature_name, value in incompatible:
        if value:
            raise CodegenError(
                f"{feature_name} reads JSON paths and cannot be combined with"
                " response_format: xml"
            )


def _context(config: RestSourceConfig) -> Dict[str, Any]:
    stream = config.stream
    eh = stream.error_handler
    auth = config.auth
    if auth.type == "oauth2" and (not auth.token_url or not auth.client_id):
        raise CodegenError("oauth2 requires token_url and client_id")
    _require_no_xml_json_paths(stream)
    params, headers, path, option_placeholders = _resolved(stream, config.options)
    windows = _static_windows(config)
    partition_strategy = stream.partition.strategy if stream.partition else "none"
    offset_param = stream.pagination.offset_param or "offset"
    page_param = stream.pagination.page_param or "page"
    scope = " ".join(auth.scope)
    return {
        "auth_type": auth.type,
        "token_url": auth.token_url,
        "token_url_repr": _py_literal(auth.token_url),
        "client_id": auth.client_id,
        "client_id_repr": _py_literal(auth.client_id),
        "scope": scope,
        "scope_repr": _py_literal(scope),
        "audience": auth.audience,
        "audience_repr": _py_literal(auth.audience),
        "oauth_extra_items": [
            (_py_literal(k), repr(v)) for k, v in auth.extra_params.items()
        ],
        "base_url": config.base_url.rstrip("/"),
        "base_url_repr": _py_literal(config.base_url.rstrip("/")),
        "path": path,
        "path_repr": _py_literal(path),
        "params_repr": _py_literal(params),
        "headers_repr": _py_literal(headers),
        "option_placeholders": option_placeholders,
        "schema_ddl": stream.schema,
        "stream_name": stream.name,
        "stream_name_repr": _py_literal(stream.name),
        "stream_name_doc": _doc_escape(stream.name),
        "stream_name_comment": _comment_escape(stream.name),
        "state_path_repr": _py_literal(f"{stream.name}_state.json"),
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
        "limit_param_repr": _py_literal(stream.pagination.limit_param),
        "limit_param_doc": _doc_escape(stream.pagination.limit_param or ""),
        "offset_param": offset_param,
        "offset_param_repr": _py_literal(offset_param),
        "offset_param_doc": _doc_escape(offset_param),
        "start_offset": stream.pagination.start_offset,
        "page_param": page_param,
        "page_param_repr": _py_literal(page_param),
        "page_param_doc": _doc_escape(page_param),
        "start_page": stream.pagination.start_page,
        "total_pages_path": list(stream.pagination.total_pages_path) or None,
        "total_pages_header": stream.pagination.total_pages_header,
        "total_pages_header_repr": _py_literal(stream.pagination.total_pages_header),
        "cursor_param": stream.pagination.cursor_param or "cursor",
        "cursor_param_repr": _py_literal(stream.pagination.cursor_param or "cursor"),
        "cursor_path": list(stream.pagination.cursor_path) or None,
        "cursor_header": stream.pagination.cursor_header,
        "cursor_header_repr": _py_literal(stream.pagination.cursor_header),
        "next_url_path": list(stream.pagination.next_url_path) or None,
        "initial_cursor_repr": repr(stream.pagination.initial_cursor),
        "incremental_mode": stream.incremental.mode,
        "cursor_param_inc": stream.incremental.cursor_param,
        "cursor_param_inc_repr": _py_literal(stream.incremental.cursor_param),
        "cursor_field": stream.incremental.cursor_field,
        "cursor_field_repr": _py_literal(stream.incremental.cursor_field),
        "windows_repr": _py_literal(windows) if windows is not None else None,
        "has_windows": bool(windows),
        "partition_strategy": partition_strategy,
        "streaming": stream.streaming,
        "response_format": stream.response_format,
        "xml_record_path_repr": _py_literal(stream.xml_record_path),
    }


def generate_core(config: RestSourceConfig) -> str:
    return _ENV.get_template("core.py.jinja").render(**_context(config))


def generate(config: RestSourceConfig) -> str:
    stream = config.stream
    if stream.streaming and (
        not stream.schema or stream.pagination.type not in ("offset", "page")
    ):
        raise CodegenError(
            "streaming requires a schema and pagination type 'offset' or 'page'"
        )
    if (
        stream.streaming
        and stream.pagination.type == "offset"
        and not stream.pagination.page_size
    ):
        raise CodegenError("streaming with offset pagination requires page_size")
    if stream.streaming and stream.incremental.mode:
        raise CodegenError("streaming does not support incremental state")
    if stream.streaming and _static_windows(config):
        raise CodegenError("streaming does not support partition strategies")
    core = generate_core(config)
    dp_wiring = _ENV.get_template("dp.py.jinja").render(**_context(config))
    return core + "\n\n" + dp_wiring
