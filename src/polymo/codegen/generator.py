"""Render standalone Lakeflow Declarative Pipelines scripts from a config."""

from __future__ import annotations

import ast as _ast
import json
import keyword
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional, Tuple
from urllib.parse import urlparse

from jinja2 import Environment, PackageLoader, StrictUndefined

from ..config import PartitionConfig, RestSourceConfig, SecretRef, UcSecretRef
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
    if cleaned and set(cleaned) == {"_"}:
        # symbol-only names (e.g. "!!!") would otherwise sanitize to a
        # colliding, ugly "___" — fall back to a real word instead.
        return "stream"
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    if keyword.iskeyword(cleaned):
        # A stream/project name like "class" or "import" would otherwise
        # sanitize to a hard Python keyword, breaking every site that
        # splices it in raw: `def class():`, `from class.client import
        # ...`, `@dp.table(name=...)` function defs, etc. — all SyntaxErrors.
        # `keyword.iskeyword` only covers hard keywords; soft keywords
        # ("match", "case", "type", "_") are valid identifiers as-is and
        # don't need this.
        cleaned = f"{cleaned}_"
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


def _marker_names(value: Any) -> set:
    """Every `OPT_*` var name embedded in `value` (a str, or dict of str).

    Used to decide which of PATH/PARAMS/HEADERS need re-evaluating in
    bundle mode after `_apply_secret_options` setattrs a resolved value
    onto the corresponding `OPT_*` global — see `_rebuild_option_globals`.
    """
    if isinstance(value, str):
        return set(_MARKER_RE.findall(value))
    if isinstance(value, dict):
        names: set = set()
        for v in value.values():
            names |= _marker_names(v)
        return names
    return set()


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


_REPLACE_ME_RHS = '"REPLACE_ME"'
_NONE_RHS = "None"


def _not_installed_message(var: str) -> str:
    """Error text for a bundle secret slot that never got a resolved value.

    Used both by `_raise_not_installed` (the generated `RuntimeError` guard)
    and by `tests.codegen.test_bundle` to assert on the exact message.
    """
    return (
        f"{var} was not installed by the pipeline — resolve secrets on the "
        "driver and pass them as reader options"
    )


def _raise_not_installed(var: str, indent: str = "    ") -> str:
    """Render a `if VAR is None: raise RuntimeError(...)` guard block.

    Used at every point a bundle-mode `str | None` secret slot (see
    `*_optional`/`rebuild_guard_vars` in `_context`) is actually read, so a
    pipeline that forgot to resolve and install the secret fails loudly
    instead of silently sending `None`/a stale value to the real API.
    `indent` is the base indentation the call site needs (the block's own
    lines nest one level deeper); the message is split across two adjacent
    string literals, mirroring `_dbx_secret`'s own raise, to keep the line
    length reasonable regardless of how long `var` is.
    """
    message = _not_installed_message(var)
    split_at = message.rfind(" ", 0, 60)
    if split_at == -1:
        split_at = len(message)
    first, second = message[: split_at + 1], message[split_at + 1 :]
    lines = [f"{indent}if {var} is None:", f"{indent}    raise RuntimeError("]
    lines.append(f"{indent}        {json.dumps(first, ensure_ascii=False)}")
    if second:
        lines.append(f"{indent}        {json.dumps(second, ensure_ascii=False)}")
    lines.append(f"{indent}    )")
    return "\n".join(lines)


def _dbx_secret_call(ref: SecretRef) -> str:
    """Render a `SecretRef` as a call to the generated `_dbx_secret` helper."""
    return f"_dbx_secret({_py_literal(ref.scope)}, {_py_literal(ref.key)})"


def _uc_secret_call(ref: UcSecretRef) -> str:
    """Render a `UcSecretRef` as a call to the generated `_uc_secret` helper."""
    return (
        f"_uc_secret({_py_literal(ref.credential)}, {_py_literal(ref.vault_url)}, "
        f"{_py_literal(ref.secret_name)})"
    )


def _bundle_secret_call(ref: SecretRef | UcSecretRef) -> str:
    """Render a secret ref as a call on the imported `client` MODULE object.

    Used only for bundles' `pipelines/<stream>.py`, which resolves secret
    refs driver-side by calling the helper through the imported `client`
    module (`from <pkg> import client`) rather than a bare module-level
    call — see the `_context` docstring for why bundles can't just bake the
    call into `client.py` itself the way single-file scripts do.
    """
    if isinstance(ref, SecretRef):
        return f"client._dbx_secret({_py_literal(ref.scope)}, {_py_literal(ref.key)})"
    return (
        f"client._uc_secret({_py_literal(ref.credential)}, "
        f"{_py_literal(ref.vault_url)}, {_py_literal(ref.secret_name)})"
    )


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


_LOCAL_STATE_SCHEMES = frozenset({"", "file"})


def _resolve_state_path(config: RestSourceConfig) -> Tuple[str, bool]:
    """Resolve the incremental state location: `(path, needs_fsspec)`.

    Mirrors the 0.x `_IncrementalTracker`: a bare path or a `file://` URL
    is a plain local file (so `/Volumes/...` and `/dbfs/...` stay POSIX
    via FUSE), any other URL scheme (`s3://`, `gs://`, `abfss://`, ...)
    goes through `fsspec`. Decided here, at generation time, so a local
    path produces zero fsspec code and a remote one gets the fsspec branch.
    """
    stream = config.stream
    raw = stream.incremental.state_path or f"{stream.name}_state.json"
    parsed = urlparse(raw)
    if parsed.scheme == "file":
        return parsed.path, False
    return raw, parsed.scheme not in _LOCAL_STATE_SCHEMES


def _page_partitions(stream) -> bool:
    """Whether `partition.strategy: pagination` fans out one partition per page.

    Mirrors 0.x `_plan_pagination_partitions`: page/offset pagination with
    a positive `page_size` and at least one `total_pages_*` /
    `total_records_*` hint the generated probe can resolve a page count
    from. Any other shape keeps the sequential loop and generates no probe
    code at all.
    """
    pagination = stream.pagination
    return (
        stream.partition.strategy == "pagination"
        and pagination.type in ("page", "offset")
        and bool(pagination.page_size)
        and any(
            (
                pagination.total_pages_path,
                pagination.total_pages_header,
                pagination.total_records_path,
                pagination.total_records_header,
            )
        )
    )


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
    option_secrets = stream.option_secrets or {}
    option_placeholder_refs = {
        var: option_secrets[name]
        for name, var in missing.items()
        if name in option_secrets
    }
    return params, headers, path, option_placeholders, option_placeholder_refs


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


def _context(config: RestSourceConfig, *, for_bundle: bool = False) -> Dict[str, Any]:
    """Build the template-rendering context for `config`.

    `for_bundle` switches how auth-secret-ref slots (API_TOKEN/API_KEY/
    CLIENT_SECRET and any ref-backed OPT_* option placeholder) render:

    - `for_bundle=False` (default, used by `generate_core`/`generate` for
      single-file scripts and the builder preview/export): a secret-ref slot
      gets a direct `_dbx_secret(...)`/`_uc_secret(...)` call as its RHS.
      Correct there because a single-file script's DataSource/reader classes
      live in `__main__` (not a real importable module), so Spark can only
      pickle them BY VALUE — the pickle snapshots the already-resolved value
      from the driver, and the module is never re-imported from scratch
      anywhere else.
    - `for_bundle=True` (used by `codegen.bundle.generate_bundle` for
      `src/<pkg>/client.py`): every secret-ref slot instead gets the same
      `"REPLACE_ME"` placeholder RHS as an *unset* slot. This is required,
      not cosmetic — `src/<pkg>` ships as an installed wheel, so Spark's
      Python workers pickle the registered DataSource class BY REFERENCE and
      reconstruct it with a fresh `import <pkg>.client`, which has no
      SparkSession/dbutils available; a module-level `_dbx_secret(...)`/
      `_uc_secret(...)` call would raise there on every single read. The
      `_dbx_secret`/`_uc_secret` helper *function definitions* are still
      emitted (gated on `has_secret_refs`/`has_uc_secret_refs`, unaffected by
      `for_bundle`) so `pipelines/<stream>.py` — which only ever runs
      driver-side — can call them directly; see `bundle_secret_slots` below.
    """
    stream = config.stream
    eh = stream.error_handler
    auth = config.auth
    if auth.type == "oauth2" and (not auth.token_url or not auth.client_id):
        raise CodegenError("oauth2 requires token_url and client_id")
    _require_no_xml_json_paths(stream)
    params, headers, path, option_placeholders, option_placeholder_refs = _resolved(
        stream, config.options
    )
    windows = _static_windows(config)
    partition_strategy = stream.partition.strategy if stream.partition else "none"
    offset_param = stream.pagination.offset_param or "offset"
    page_param = stream.pagination.page_param or "page"
    scope = " ".join(auth.scope)
    base_url = config.base_url.rstrip("/")
    incremental = stream.incremental
    state_path, state_remote = _resolve_state_path(config)
    state_key = incremental.state_key or f"{stream.name}@{base_url}"
    page_partitions = _page_partitions(stream)
    # Static windows carry either `path` (endpoints) or `extra_params`
    # (param_range), never both — the reader template merges pushed filter
    # params differently for each shape.
    windows_kind = None
    if windows:
        windows_kind = "path" if "path" in windows[0] else "extra_params"

    def _auth_secret_rhs(auth_type: str) -> Tuple[str, str, bool]:
        """RHS for one auth secret slot: `_dbx_secret(...)`, `_uc_secret(...)`,
        or the `"REPLACE_ME"` placeholder. `secret`/`uc_secret` are mutually
        exclusive (enforced in `AuthConfig` parsing), so at most one applies.

        When `for_bundle` and a ref is present, the slot can't hold either
        the call (session-less worker, see the docstring above) or a
        harmless-looking `"REPLACE_ME"` (which would ship the literal string
        to the real API instead of failing loudly) — it gets `None` instead,
        typed `str | None`, with a `RuntimeError` guard at the point of use
        (see `*_optional` below) so a pipeline that forgot to resolve and
        install the secret fails clearly instead of leaking a placeholder.
        Returns `(rhs, type_annotation, optional)`.
        """
        if auth.type != auth_type:
            return _REPLACE_ME_RHS, "str", False
        if for_bundle:
            if auth.secret or auth.uc_secret:
                return _NONE_RHS, "str | None", True
            return _REPLACE_ME_RHS, "str", False
        if auth.secret:
            return _dbx_secret_call(auth.secret), "str", False
        if auth.uc_secret:
            return _uc_secret_call(auth.uc_secret), "str", False
        return _REPLACE_ME_RHS, "str", False

    api_token_rhs, api_token_type, api_token_optional = _auth_secret_rhs("bearer")
    api_key_rhs, api_key_type, api_key_optional = _auth_secret_rhs("api_key")
    client_secret_rhs, client_secret_type, client_secret_optional = _auth_secret_rhs(
        "oauth2"
    )

    def _option_placeholder_spec(var: str) -> Tuple[str, str, str]:
        """Returns `(var, rhs, type_annotation)` for one OPT_* placeholder.

        Mirrors `_auth_secret_rhs` above: a ref-backed slot renders as
        `None`/`str | None` when `for_bundle` (guarded in
        `_rebuild_option_literals`, see `rebuild_guard_vars` below), or as a
        direct `_dbx_secret(...)` call otherwise; an unreferenced or
        ref-less slot always stays the `"REPLACE_ME"` placeholder.
        """
        ref = option_placeholder_refs.get(var)
        if for_bundle:
            if ref is not None:
                return var, _NONE_RHS, "str | None"
            return var, _REPLACE_ME_RHS, "str"
        if ref is not None:
            return var, _dbx_secret_call(ref), "str"
        return var, _REPLACE_ME_RHS, "str"

    option_placeholder_specs = [
        _option_placeholder_spec(var) for var in option_placeholders
    ]
    # option_secrets (the `{{ options.* }}` placeholder path) stays
    # scope-only — see the docstring on `StreamConfig.option_secrets` — so
    # only the top-level auth slot can ever need the `_uc_secret` helper.
    has_secret_refs = bool(
        (auth.type in ("bearer", "api_key", "oauth2") and auth.secret)
        or option_placeholder_refs
    )
    has_uc_secret_refs = bool(
        auth.type in ("bearer", "api_key", "oauth2") and auth.uc_secret
    )
    # Driver-side resolution list for bundles: (module attribute name, call
    # expression reaching the helper through the imported `client` module
    # object, e.g. `client._dbx_secret("scope", "key")`). Computed
    # regardless of `for_bundle` (cheap, and only ever consumed by
    # `codegen.bundle`'s bundle_ctx) — see `templates/bundle/pipeline.py.jinja`
    # (resolves these driver-side and threads them through as DataSource
    # reader options) and `templates/bundle/source.py.jinja` (installs them
    # onto `client`'s module globals on each worker before fetching).
    bundle_secret_slots: List[Tuple[str, str]] = []
    for slot_var, slot_auth_type in (
        ("API_TOKEN", "bearer"),
        ("API_KEY", "api_key"),
        ("CLIENT_SECRET", "oauth2"),
    ):
        if auth.type != slot_auth_type:
            continue
        if auth.secret:
            bundle_secret_slots.append((slot_var, _bundle_secret_call(auth.secret)))
        elif auth.uc_secret:
            bundle_secret_slots.append((slot_var, _bundle_secret_call(auth.uc_secret)))
    for var in option_placeholders:
        ref = option_placeholder_refs.get(var)
        if ref is not None:
            bundle_secret_slots.append((var, _bundle_secret_call(ref)))
    # Bundle-mode-only fix: HEADERS/PARAMS/PATH literals that embed an
    # `OPT_*` placeholder for a driver-resolved secret (i.e. the var also
    # appears in `bundle_secret_slots` above) are otherwise frozen at
    # import time — `_apply_secret_options` (source.py.jinja) setattrs the
    # resolved value onto the `OPT_*` global itself, but that setattr never
    # reaches an f-string/dict literal that already evaluated. Naming here
    # exactly which of PATH/PARAMS/HEADERS need re-evaluating (and only
    # those) lets `core.py.jinja` emit a `_rebuild_option_literals()` that
    # re-runs the same literal expressions, called from
    # `_apply_secret_options` after the setattr loop. Empty (and thus a
    # no-op everywhere) unless `for_bundle`, so single-file output is
    # unaffected.
    secret_backed_option_vars = set(option_placeholder_refs.keys())
    rebuild_option_globals: List[str] = []
    rebuild_marker_names: set = set()
    if for_bundle:
        if _marker_names(path) & secret_backed_option_vars:
            rebuild_option_globals.append("PATH")
            rebuild_marker_names |= _marker_names(path)
        if _marker_names(params) & secret_backed_option_vars:
            rebuild_option_globals.append("PARAMS")
            rebuild_marker_names |= _marker_names(params)
        if _marker_names(headers) & secret_backed_option_vars:
            rebuild_option_globals.append("HEADERS")
            rebuild_marker_names |= _marker_names(headers)
    # Which of the OPT_* vars rebuilt above are still None (never installed
    # by the pipeline) needs a RuntimeError guard right before the rebuild —
    # see `_not_installed_message` and `core.py.jinja`'s
    # `_rebuild_option_literals`. Scoped to just the vars that are both
    # ref-backed (optional=True, so really can be None) and actually
    # referenced by one of the literals being rebuilt.
    rebuild_guard_vars = sorted(rebuild_marker_names & secret_backed_option_vars)
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
        "api_key_in": auth.api_key_in,
        "api_key_name_repr": _py_literal(auth.api_key_name),
        "oauth_extra_items": [
            (_py_literal(k), repr(v)) for k, v in auth.extra_params.items()
        ],
        "base_url": base_url,
        "base_url_repr": _py_literal(base_url),
        "path": path,
        "path_repr": _py_literal(path),
        "params_repr": _py_literal(params),
        "headers_repr": _py_literal(headers),
        "option_placeholders": option_placeholders,
        "option_placeholder_specs": option_placeholder_specs,
        "api_token_rhs": api_token_rhs,
        "api_token_type": api_token_type,
        "api_token_optional": api_token_optional,
        "api_key_rhs": api_key_rhs,
        "api_key_type": api_key_type,
        "api_key_optional": api_key_optional,
        "client_secret_rhs": client_secret_rhs,
        "client_secret_type": client_secret_type,
        "client_secret_optional": client_secret_optional,
        "raise_not_installed": _raise_not_installed,
        "has_secret_refs": has_secret_refs,
        "has_uc_secret_refs": has_uc_secret_refs,
        "bundle_secret_slots": bundle_secret_slots,
        "rebuild_option_globals": rebuild_option_globals,
        "rebuild_guard_vars": rebuild_guard_vars,
        "schema_ddl": stream.schema,
        "stream_name": stream.name,
        "stream_name_repr": _py_literal(stream.name),
        "stream_name_doc": _doc_escape(stream.name),
        "func_name": _identifier(stream.name),
        # Databricks requires unquoted SQL identifiers for dp table names.
        "table_name_repr": _py_literal(_identifier(stream.name)),
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
        "total_records_path": list(stream.pagination.total_records_path) or None,
        "total_records_header": stream.pagination.total_records_header,
        "total_records_header_repr": _py_literal(
            stream.pagination.total_records_header
        ),
        "page_partitions": page_partitions,
        "cursor_param": stream.pagination.cursor_param or "cursor",
        "cursor_param_repr": _py_literal(stream.pagination.cursor_param or "cursor"),
        "cursor_path": list(stream.pagination.cursor_path) or None,
        "cursor_header": stream.pagination.cursor_header,
        "cursor_header_repr": _py_literal(stream.pagination.cursor_header),
        "next_url_path": list(stream.pagination.next_url_path) or None,
        "initial_cursor_repr": repr(stream.pagination.initial_cursor),
        "incremental": incremental.enabled,
        "incremental_mode_repr": _py_literal(incremental.mode),
        "cursor_param_inc_repr": _py_literal(incremental.cursor_param),
        "cursor_field_repr": _py_literal(incremental.cursor_field),
        "cursor_field_dotted": "." in (incremental.cursor_field or ""),
        "state_path": state_path,
        "state_path_repr": _py_literal(state_path),
        "state_remote": state_remote,
        "state_key_repr": _py_literal(state_key),
        "start_value_repr": _py_literal(incremental.start_value),
        "windows_repr": _py_literal(windows) if windows is not None else None,
        "has_windows": bool(windows),
        "windows_kind": windows_kind,
        "pushdown": bool(stream.pushdown_params),
        "pushdown_params_repr": _py_literal(dict(stream.pushdown_params)),
        "partition_strategy": partition_strategy,
        "streaming": stream.streaming,
        "response_format": stream.response_format,
        "xml_record_path_repr": _py_literal(stream.xml_record_path),
        # Overridden by `codegen.bundle` when rendering `dp.py.jinja` as a
        # standalone pipeline file for a Databricks Asset Bundle project
        # (see `_bundle_import_names` there); left falsy here so the
        # concatenated core+dp output of `generate()` is unaffected.
        "bundle_pkg": None,
        "bundle_imports": [],
    }


def generate_core(config: RestSourceConfig) -> str:
    return _ENV.get_template("core.py.jinja").render(**_context(config))


def validate_dp_wiring(config: RestSourceConfig) -> None:
    """Raise `CodegenError` if `config` can't be expressed as a `dp.table`.

    Shared by `generate()` (single-file export) and
    `codegen.bundle.generate_bundle()` (Asset Bundle project) so the two
    can never drift on which configs are rejected.
    """
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
    if stream.streaming and stream.incremental.enabled:
        raise CodegenError("streaming does not support incremental state")
    if stream.streaming and stream.partition.strategy != "none":
        raise CodegenError("streaming does not support partition strategies")
    if stream.streaming and stream.pushdown_params:
        raise CodegenError(
            "streaming does not support filter pushdown (pushdown_params);"
            " Spark only pushes filters into batch reads"
        )


def generate(config: RestSourceConfig) -> str:
    validate_dp_wiring(config)
    core = generate_core(config)
    dp_wiring = _ENV.get_template("dp.py.jinja").render(**_context(config))
    return core + "\n\n" + dp_wiring
