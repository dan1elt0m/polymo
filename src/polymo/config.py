"""Configuration loading and validation for REST-backed data sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Literal,
    Optional,
    Mapping,
    Sequence,
    Tuple,
)
import re

# pyspark is optional at generation time (it only ships in the `builder`
# extra): a bare `pip install polymo` must be able to `import polymo` and
# call `generate()`, including for configs with a `schema` DDL string, so
# nothing in this module may import pyspark eagerly at module load time.
# `parse_schema_struct` (and its helpers below) import pyspark lazily,
# inside the functions that actually need real Spark type objects; the
# config-parsing validation path (`_validate_ddl`) is deliberately kept
# pyspark-free (see `_validate_ddl_syntax`) since it runs on every
# schema-bearing config, including in `generate()`.
if TYPE_CHECKING:
    from pyspark.sql.types import StructType


class ConfigError(ValueError):
    """Raised when the user-provided YAML configuration is invalid."""


_REDACTED_TOKENS = {
    "***",
    "****",
    "*****",
    "******",
    "[redacted]",
    "<redacted>",
    "redacted",
}


def _resolve_secret_value(raw: Any) -> Tuple[Optional[str], bool]:
    """Attempt to coerce a secret value into a usable string.

    Returns a tuple of (value, is_redacted). When ``is_redacted`` is True,
    the caller should treat the value as intentionally masked and request the
    real secret again. The function tries a variety of access patterns to
    support secret wrappers (e.g. Databricks DBUtils) without ever stringifying
    the secret prematurely.
    """

    seen: set[int] = set()

    def _inner(value: Any) -> Tuple[Optional[str], bool]:
        if value is None:
            return None, False

        obj_id = id(value)
        if obj_id in seen:
            return None, False
        seen.add(obj_id)

        if isinstance(value, str):
            trimmed = value.strip()
            if not trimmed:
                return None, False
            if trimmed.startswith("{{") and trimmed.endswith("}}"):
                return None, False

            lowered = trimmed.lower()
            if lowered in _REDACTED_TOKENS or set(trimmed) <= {"*"}:
                return None, True

            return trimmed, False

        if isinstance(value, (bytes, bytearray)):
            try:
                decoded = bytes(value).decode()
            except UnicodeDecodeError:
                decoded = bytes(value).decode("utf-8", errors="ignore")
            return _inner(decoded)

        if callable(value):
            try:
                resolved = value()
            except TypeError:
                resolved = None
            if resolved is not None:
                return _inner(resolved)

        attribute_candidates = (
            "value",
            "secret",
            "get",
            "get_value",
            "getSecretValue",
            "getSecret",
            "get_secret_value",
        )
        for attr_name in attribute_candidates:
            attr = getattr(value, attr_name, None)
            if attr is None:
                continue
            if callable(attr):
                try:
                    resolved = attr()
                except TypeError:
                    continue
            else:
                resolved = attr
            resolved_value, was_redacted = _inner(resolved)
            if resolved_value is not None or was_redacted:
                return resolved_value, was_redacted

        try:
            text_repr = str(value)
        except Exception:
            text_repr = None
        if text_repr is not None and text_repr is not value:
            return _inner(text_repr)

        return None, False

    return _inner(raw)


@dataclass(frozen=True)
class SecretRef:
    """A reference to a secret stored in a Databricks secret scope.

    Configs carry ONLY this reference (`scope` + `key`) — never the secret
    value itself. Generated code resolves it on the driver via the
    `_dbx_secret(scope, key)` helper (see `polymo.codegen.generator`).
    """

    scope: str
    key: str


@dataclass(frozen=True)
class UcSecretRef:
    """A reference to a secret resolved via a Unity Catalog service
    credential + Azure Key Vault, instead of a Databricks secret scope.

    Configs carry ONLY this reference (`credential`, `vault_url`,
    `secret_name`) — never the secret value itself. Generated code resolves
    it on the driver via the `_uc_secret(credential, vault_url,
    secret_name)` helper (see `polymo.codegen.generator`), which calls
    `dbutils.credentials.getServiceCredentialsProvider(credential)` and uses
    it to authenticate an Azure Key Vault `SecretClient`.
    """

    credential: str
    vault_url: str
    secret_name: str


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration for REST requests."""

    type: Literal["none", "bearer", "oauth2", "api_key"] = "none"
    token: str | None = None
    token_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scope: Tuple[str, ...] = field(default_factory=tuple)
    audience: str | None = None
    extra_params: Mapping[str, Any] = field(default_factory=dict)
    # api_key auth: the key VALUE is never stored (same policy as bearer's
    # `token`) — only where it goes (`api_key_in`) and its header/query
    # name (`api_key_name`) are kept.
    api_key_in: Literal["header", "query"] | None = None
    api_key_name: str | None = None
    # Optional Databricks secret-scope reference for the auth secret slot
    # (bearer token / api_key value / oauth2 client_secret — one slot each).
    # When set, codegen resolves it via `_dbx_secret(...)` instead of the
    # `"REPLACE_ME"` placeholder. Mutually exclusive with `uc_secret`.
    secret: SecretRef | None = None
    # Optional Unity Catalog service-credential + Key Vault reference for
    # the same auth secret slot. When set, codegen resolves it via
    # `_uc_secret(...)` instead. Mutually exclusive with `secret`.
    uc_secret: UcSecretRef | None = None


@dataclass(frozen=True)
class PaginationConfig:
    """Pagination strategy definition."""

    type: Literal["none", "link_header", "offset", "cursor", "page"] = "none"
    page_size: Optional[int] = None
    limit_param: Optional[str] = None
    offset_param: Optional[str] = None
    start_offset: int = 0
    page_param: Optional[str] = None
    start_page: int = 1
    cursor_param: Optional[str] = None
    cursor_path: Tuple[str, ...] = field(default_factory=tuple)
    next_url_path: Tuple[str, ...] = field(default_factory=tuple)
    cursor_header: Optional[str] = None
    initial_cursor: Optional[str] = None
    stop_on_empty_response: bool = True
    total_pages_path: Tuple[str, ...] = field(default_factory=tuple)
    total_pages_header: Optional[str] = None
    total_records_path: Tuple[str, ...] = field(default_factory=tuple)
    total_records_header: Optional[str] = None


@dataclass(frozen=True)
class SchemaConfig:
    """Schema hints supplied by the user."""

    infer: bool = False
    ddl: str | None = None


@dataclass(frozen=True)
class IncrementalConfig:
    """Incremental cursor tracking between runs.

    Enabled iff both `cursor_param` and `cursor_field` are set (`mode` is a
    free-text label stored alongside the cursor in the state file). The
    remaining fields mirror the 0.x reader options of the same name:
    `state_path` (local path or fsspec URL, default `<stream>_state.json`),
    `start_value` (seed used only when no stored cursor exists) and
    `state_key` (entry key in the state file, default `<stream>@<base_url>`).
    """

    mode: Optional[str] = None
    cursor_param: Optional[str] = None
    cursor_field: Optional[str] = None
    state_path: Optional[str] = None
    start_value: Optional[str] = None
    state_key: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return bool(self.cursor_param and self.cursor_field)


@dataclass(frozen=True)
class RecordSelectorConfig:
    """Record selector configuration inspired by Airbyte's builder."""

    field_path: List[str] = field(default_factory=list)
    record_filter: Optional[str] = None
    cast_to_schema_types: bool = False


@dataclass(frozen=True)
class BackoffConfig:
    """Retry backoff configuration for the REST error handler."""

    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 30.0
    multiplier: float = 2.0


def _default_retry_statuses() -> Tuple[str, ...]:
    return ("5XX", "429")


@dataclass(frozen=True)
class ErrorHandlerConfig:
    """Controls how HTTP and network errors are handled."""

    max_retries: int = 5
    retry_statuses: Tuple[str, ...] = field(default_factory=_default_retry_statuses)
    retry_on_timeout: bool = True
    retry_on_connection_errors: bool = True
    backoff: BackoffConfig = field(default_factory=BackoffConfig)


@dataclass(frozen=True)
class PartitionConfig:
    """Partition strategy configuration."""

    strategy: Literal["none", "pagination", "param_range", "endpoints"] = "none"
    param: Optional[str] = None
    values: Optional[str | Sequence[str]] = None
    range_start: Optional[Any] = None  # Can be int or str for date ranges
    range_end: Optional[Any] = None  # Can be int or str for date ranges
    range_step: Optional[int] = None
    range_kind: Optional[Literal["numeric", "date"]] = None
    value_template: Optional[str] = None
    extra_template: Optional[str] = None
    endpoints: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class StreamConfig:
    """Definition of a logical stream within the REST connector."""

    name: str  # internal identifier (derived from path if not provided)
    path: str
    params: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, str] = field(default_factory=dict)
    pagination: PaginationConfig = field(default_factory=PaginationConfig)
    incremental: IncrementalConfig = field(default_factory=IncrementalConfig)
    infer_schema: bool = True
    schema: str | None = None
    record_selector: RecordSelectorConfig = field(default_factory=RecordSelectorConfig)
    error_handler: ErrorHandlerConfig = field(default_factory=ErrorHandlerConfig)
    partition: PartitionConfig = field(default_factory=PartitionConfig)
    streaming: bool = False
    response_format: Literal["json", "xml"] = "json"
    xml_record_path: Optional[str] = None
    # Filter pushdown: DataFrame column name -> API query parameter name. An
    # equality filter on a mapped column is sent to the API as that query
    # parameter instead of being evaluated by Spark after the read.
    pushdown_params: Dict[str, str] = field(default_factory=dict)
    # Databricks secret-scope references for `{{ options.<name> }}`
    # placeholders, keyed by option name. A name that isn't actually
    # referenced as an unresolved option is harmless (simply unused).
    # Scope-only by design: unlike `AuthConfig.secret`/`AuthConfig.uc_secret`
    # (one slot each, so either source is unambiguous), a per-option UC
    # secret source would need a second mapping here to stay unambiguous
    # per name — not worth the complexity for what's a power-user escape
    # hatch already. Use `auth.uc_secret` for the primary auth secret slot.
    option_secrets: Mapping[str, SecretRef] = field(default_factory=dict)


@dataclass(frozen=True)
class RestSourceConfig:
    """Top-level configuration mapping for the connector."""

    version: str
    base_url: str
    auth: AuthConfig
    stream: StreamConfig
    options: Dict[str, Any] = field(default_factory=dict)


def parse_config(
    raw: Any,
    token: str | None = None,
    options: Optional[Mapping[str, Any]] = None,
) -> RestSourceConfig:
    """Validate a configuration object previously parsed from YAML.

    Auth info is provided separately via the token argument.
    """

    if not isinstance(raw, dict):
        raise ConfigError("Configuration root must be a mapping")

    version = str(raw.get("version"))
    if version not in {"0.1"}:
        raise ConfigError("Only version '0.1' configurations are supported")

    source = raw.get("source")
    if not isinstance(source, dict):
        raise ConfigError("'source' section must be provided")

    if source.get("type") != "rest":
        raise ConfigError("Only REST sources are supported for now")

    runtime_options: Dict[str, Any] = dict(options or {})

    auth = _parse_auth_config(source.get("auth"), token, runtime_options)

    base_url = source.get("base_url")
    if not isinstance(base_url, str) or not base_url:
        raise ConfigError("'source.base_url' must be a non-empty string")

    # Only support single stream format
    stream_raw = raw.get("stream")
    if not stream_raw:
        raise ConfigError("A stream must be defined")

    stream = _parse_stream(stream_raw)

    if auth.type == "api_key" and auth.api_key_in == "query":
        _check_api_key_query_collision(auth, stream)

    return RestSourceConfig(
        version=version,
        base_url=base_url.rstrip("/"),
        auth=auth,
        stream=stream,
        options=runtime_options,
    )


def _parse_secret_ref(raw: Any, field_label: str) -> Optional[SecretRef]:
    """Parse a `{"scope": ..., "key": ...}` Databricks secret reference.

    Returns None when `raw` is None (the slot has no secret reference).
    Both `scope` and `key` must be non-empty strings when a reference is
    provided — this is a reference only, never a secret value.
    """
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ConfigError(f"'{field_label}' must be a mapping with 'scope' and 'key'")

    scope_raw = raw.get("scope")
    key_raw = raw.get("key")
    scope = scope_raw.strip() if isinstance(scope_raw, str) else None
    key = key_raw.strip() if isinstance(key_raw, str) else None
    if not scope or not key:
        raise ConfigError(f"'{field_label}' requires non-empty 'scope' and 'key'")

    return SecretRef(scope=scope, key=key)


def _secret_ref_to_dict(ref: SecretRef) -> Dict[str, str]:
    return {"scope": ref.scope, "key": ref.key}


def _parse_uc_secret_ref(raw: Any, field_label: str) -> Optional[UcSecretRef]:
    """Parse a `{"credential": ..., "vault_url": ..., "secret_name": ...}`
    Unity Catalog service-credential reference.

    Returns None when `raw` is None (the slot has no UC secret reference).
    All three fields must be non-empty strings when a reference is
    provided — this is a reference only, never a secret value.
    """
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        raise ConfigError(
            f"'{field_label}' must be a mapping with 'credential', 'vault_url',"
            " and 'secret_name'"
        )

    for secret_field in ("value", "key", "token"):
        if secret_field in raw:
            raise ConfigError(
                f"'{field_label}' is a reference only; it must not contain a"
                f" '{secret_field}' key with an actual secret value"
            )

    credential_raw = raw.get("credential")
    vault_url_raw = raw.get("vault_url")
    secret_name_raw = raw.get("secret_name")
    credential = credential_raw.strip() if isinstance(credential_raw, str) else None
    vault_url = vault_url_raw.strip() if isinstance(vault_url_raw, str) else None
    secret_name = secret_name_raw.strip() if isinstance(secret_name_raw, str) else None
    if not credential or not vault_url or not secret_name:
        raise ConfigError(
            f"'{field_label}' requires non-empty 'credential', 'vault_url', and"
            " 'secret_name'"
        )

    return UcSecretRef(
        credential=credential, vault_url=vault_url, secret_name=secret_name
    )


def _uc_secret_ref_to_dict(ref: UcSecretRef) -> Dict[str, str]:
    return {
        "credential": ref.credential,
        "vault_url": ref.vault_url,
        "secret_name": ref.secret_name,
    }


def _parse_option_secrets(raw: Any) -> Dict[str, SecretRef]:
    if raw is None:
        return {}
    if not isinstance(raw, Mapping):
        raise ConfigError("'stream.option_secrets' must be a mapping when provided")

    result: Dict[str, SecretRef] = {}
    for name, ref_raw in raw.items():
        ref = _parse_secret_ref(ref_raw, f"stream.option_secrets.{name}")
        if ref is None:
            raise ConfigError(
                f"'stream.option_secrets.{name}' requires non-empty 'scope' and 'key'"
            )
        result[str(name)] = ref
    return result


def _reserved_query_param_names(stream: StreamConfig) -> Dict[str, str]:
    """Query parameter names the generated script populates itself.

    Maps each reserved name to a human-readable label of where it comes
    from, for use in the api_key/query collision error message: the
    built-in names (see `_builtin_query_param_names`) plus every
    `pushdown_params` target.
    """
    reserved = _builtin_query_param_names(stream)
    for column, param in stream.pushdown_params.items():
        reserved.setdefault(param, f"pushdown_params.{column}")
    return reserved


def _builtin_query_param_names(stream: StreamConfig) -> Dict[str, str]:
    """Query parameter names the generated fetch loop assigns itself.

    Only includes names that are actually applied at request time for this
    stream's configuration — e.g. `pagination.offset_param` is irrelevant
    (and excluded) unless `pagination.type == "offset"`, since that's the
    only pagination type whose fetch loop ever assigns it into `params`.
    Mirrors the branches in `core.py.jinja` exactly.
    """
    reserved: Dict[str, str] = {}
    pagination = stream.pagination

    if pagination.type == "offset":
        if pagination.offset_param:
            reserved[pagination.offset_param] = "pagination.offset_param"
        if pagination.limit_param:
            reserved[pagination.limit_param] = "pagination.limit_param"
    elif pagination.type == "page":
        if pagination.page_param:
            reserved[pagination.page_param] = "pagination.page_param"
        if pagination.limit_param:
            reserved[pagination.limit_param] = "pagination.limit_param"
    elif pagination.type == "cursor" and not pagination.next_url_path:
        # The next_url_path branch never assigns a named cursor param into
        # `params` (it follows a server-supplied URL instead), so only the
        # plain-cursor branch's default-resolved name is reserved.
        cursor_param = pagination.cursor_param or "cursor"
        reserved[cursor_param] = "pagination.cursor_param"
        if pagination.limit_param:
            reserved[pagination.limit_param] = "pagination.limit_param"

    if stream.incremental.cursor_param:
        reserved[stream.incremental.cursor_param] = "incremental.cursor_param"

    if stream.partition.strategy == "param_range" and stream.partition.param:
        reserved[stream.partition.param] = "partition.param"

    return reserved


def _check_pushdown_collisions(stream: StreamConfig) -> None:
    """A pushed filter param must not mask a param the fetch loop assigns.

    Pushed values are applied with `params.update(...)` before the
    pagination / incremental params are set, so a shared name would either
    be silently overwritten (pagination) or double-assigned (cursor); both
    are configuration mistakes, rejected up front. Two columns mapping to
    the same param would likewise overwrite each other.
    """
    builtin = _builtin_query_param_names(stream)
    seen: Dict[str, str] = {}
    for column, param in stream.pushdown_params.items():
        label = builtin.get(param)
        if label:
            raise ConfigError(
                f"'stream.pushdown_params.{column}' ({param!r}) collides with"
                f" {label} ({param!r}); choose a different query parameter"
            )
        if param in seen:
            raise ConfigError(
                f"'stream.pushdown_params.{column}' and"
                f" 'stream.pushdown_params.{seen[param]}' both map to {param!r}"
            )
        seen[param] = column


def _check_api_key_query_collision(auth: AuthConfig, stream: StreamConfig) -> None:
    """Guard against a query-placed api_key name masking a real request
    param (or being masked by one — either way, one of the two values is
    silently dropped since they'd share a single dict key)."""
    reserved = _reserved_query_param_names(stream)
    label = reserved.get(auth.api_key_name or "")
    if label:
        raise ConfigError(
            f"'source.auth.name' ({auth.api_key_name!r}) collides with"
            f" {label} ({auth.api_key_name!r}); choose a different query"
            " parameter name for api_key auth"
        )


def config_to_dict(config: RestSourceConfig) -> Dict[str, Any]:
    """Convert a RestSourceConfig instance into a canonical plain dict.

    Includes auth type (without secret) so UIs can remember selection.
    """

    source: Dict[str, Any] = {
        "type": "rest",
        "base_url": config.base_url,
    }
    if config.auth.type == "bearer":
        # Expose only the auth type, never the token.
        source["auth"] = {"type": "bearer"}
        if config.auth.secret:
            source["auth"]["secret"] = _secret_ref_to_dict(config.auth.secret)
        if config.auth.uc_secret:
            source["auth"]["uc_secret"] = _uc_secret_ref_to_dict(config.auth.uc_secret)
    elif config.auth.type == "api_key":
        # Expose placement and name, never the key value (which isn't
        # stored on AuthConfig in the first place).
        source["auth"] = {
            "type": "api_key",
            "in": config.auth.api_key_in,
            "name": config.auth.api_key_name,
        }
        if config.auth.secret:
            source["auth"]["secret"] = _secret_ref_to_dict(config.auth.secret)
        if config.auth.uc_secret:
            source["auth"]["uc_secret"] = _uc_secret_ref_to_dict(config.auth.uc_secret)
    elif config.auth.type == "oauth2":
        auth_block: Dict[str, Any] = {"type": "oauth2"}
        if config.auth.token_url:
            auth_block["token_url"] = config.auth.token_url
        if config.auth.client_id:
            auth_block["client_id"] = config.auth.client_id
        if config.auth.scope:
            auth_block["scope"] = list(config.auth.scope)
        if config.auth.audience:
            auth_block["audience"] = config.auth.audience
        if config.auth.extra_params:
            auth_block["extra_params"] = dict(config.auth.extra_params)
        if config.auth.secret:
            auth_block["secret"] = _secret_ref_to_dict(config.auth.secret)
        if config.auth.uc_secret:
            auth_block["uc_secret"] = _uc_secret_ref_to_dict(config.auth.uc_secret)
        source["auth"] = auth_block

    stream = config.stream
    stream_dict: Dict[str, Any] = {
        # 'name' becomes the dp table name (sanitized to a SQL identifier
        # at codegen time); always included so the builder UI's "Table
        # name" field round-trips through /api/validate.
        "name": stream.name,
        "path": stream.path,
        "infer_schema": stream.infer_schema,
        "schema": stream.schema,
        "pagination": _pagination_to_dict(stream.pagination),
        "streaming": stream.streaming,
        "response_format": stream.response_format,
        "xml_record_path": stream.xml_record_path,
    }

    if stream.params:
        stream_dict["params"] = dict(stream.params)

    if stream.headers:
        stream_dict["headers"] = dict(stream.headers)

    if stream.option_secrets:
        stream_dict["option_secrets"] = {
            name: _secret_ref_to_dict(ref)
            for name, ref in stream.option_secrets.items()
        }

    if stream.pushdown_params:
        stream_dict["pushdown_params"] = dict(stream.pushdown_params)

    # Always include incremental object, even if all fields are null
    incremental: Dict[str, Any] = {
        "mode": stream.incremental.mode,
        "cursor_param": stream.incremental.cursor_param,
        "cursor_field": stream.incremental.cursor_field,
        "state_path": stream.incremental.state_path,
        "start_value": stream.incremental.start_value,
        "state_key": stream.incremental.state_key,
    }
    stream_dict["incremental"] = incremental

    selector = stream.record_selector
    stream_dict["record_selector"] = {
        "field_path": list(selector.field_path),
        "record_filter": selector.record_filter,
        "cast_to_schema_types": selector.cast_to_schema_types,
    }

    error_handler = stream.error_handler
    stream_dict["error_handler"] = {
        "max_retries": error_handler.max_retries,
        "retry_statuses": list(error_handler.retry_statuses),
        "retry_on_timeout": error_handler.retry_on_timeout,
        "retry_on_connection_errors": error_handler.retry_on_connection_errors,
        "backoff": {
            "initial_delay_seconds": error_handler.backoff.initial_delay_seconds,
            "max_delay_seconds": error_handler.backoff.max_delay_seconds,
            "multiplier": error_handler.backoff.multiplier,
        },
    }

    partition = stream.partition
    partition_values = partition.values
    if isinstance(partition_values, tuple):
        partition_values = list(partition_values)

    stream_dict["partition"] = {
        "strategy": partition.strategy,
        "param": partition.param,
        "values": partition_values,
        "range_start": partition.range_start,
        "range_end": partition.range_end,
        "range_step": partition.range_step,
        "range_kind": partition.range_kind,
        "value_template": partition.value_template,
        "extra_template": partition.extra_template,
        "endpoints": list(partition.endpoints),
    }

    return {
        "version": config.version,
        "source": source,
        "stream": stream_dict,
    }


def _parse_auth_config(
    raw_auth: Any,
    runtime_token: Optional[str],
    runtime_options: Dict[str, Any],
) -> AuthConfig:
    token_value = (
        runtime_token.strip()
        if isinstance(runtime_token, str) and runtime_token.strip()
        else None
    )

    if raw_auth is None:
        if token_value:
            return AuthConfig(type="bearer", token=token_value)
        return AuthConfig()

    if not isinstance(raw_auth, Mapping):
        raise ConfigError("'source.auth' must be a mapping when provided")

    auth_type = raw_auth.get("type") or ("bearer" if token_value else "none")
    if auth_type not in {"none", "bearer", "oauth2", "api_key"}:
        raise ConfigError(f"Unsupported auth type: {auth_type}")

    if auth_type == "none":
        return AuthConfig()

    auth_secret = _parse_secret_ref(raw_auth.get("secret"), "source.auth.secret")
    auth_uc_secret = _parse_uc_secret_ref(
        raw_auth.get("uc_secret"), "source.auth.uc_secret"
    )
    if auth_secret and auth_uc_secret:
        raise ConfigError(
            "'source.auth.secret' and 'source.auth.uc_secret' are mutually"
            " exclusive; choose one secret source"
        )

    if auth_type == "bearer":
        raw_token = raw_auth.get("token")
        raw_token = raw_token.strip() if isinstance(raw_token, str) else None
        token = token_value or raw_token
        return AuthConfig(
            type="bearer", token=token, secret=auth_secret, uc_secret=auth_uc_secret
        )

    if auth_type == "api_key":
        for secret_field in ("value", "key", "token"):
            if secret_field in raw_auth:
                raise ConfigError(
                    "api_key values are supplied at runtime and are never stored"
                    " in configs"
                )

        api_key_in = raw_auth.get("in")
        if api_key_in not in {"header", "query"}:
            raise ConfigError(
                "'source.auth.in' must be either 'header' or 'query' for api_key auth"
            )

        raw_name = raw_auth.get("name")
        api_key_name = raw_name.strip() if isinstance(raw_name, str) else None
        if not api_key_name:
            raise ConfigError("'source.auth.name' is required for api_key auth")

        return AuthConfig(
            type="api_key",
            api_key_in=api_key_in,
            api_key_name=api_key_name,
            secret=auth_secret,
            uc_secret=auth_uc_secret,
        )

    # OAuth2 client credentials
    token_url = raw_auth.get("token_url")

    client_id = raw_auth.get("client_id")
    client_secret_raw = raw_auth.get("client_secret")
    client_secret, _ = _resolve_secret_value(client_secret_raw)

    secret_from_options_raw = runtime_options.pop("oauth_client_secret", None)
    secret_from_options, _ = _resolve_secret_value(secret_from_options_raw)

    client_secret = client_secret or token_value or secret_from_options

    scope_raw = raw_auth.get("scope")
    scope: Tuple[str, ...] = ()
    if isinstance(scope_raw, str):
        scope = tuple(part for part in scope_raw.replace(",", " ").split() if part)
    elif isinstance(scope_raw, (list, tuple)):
        collected: List[str] = []
        for item in scope_raw:
            if not isinstance(item, str):
                raise ConfigError("Each scope entry must be a string")
            trimmed = item.strip()
            if trimmed:
                collected.append(trimmed)
        scope = tuple(collected)
    elif scope_raw not in (None, {}):
        raise ConfigError("'source.auth.scope' must be a string or list of strings")

    audience_raw = raw_auth.get("audience")
    audience = (
        audience_raw.strip()
        if isinstance(audience_raw, str) and audience_raw.strip()
        else None
    )

    extra_params_raw = raw_auth.get("extra_params")
    extra_params: Dict[str, Any] = {}
    if extra_params_raw is not None:
        if not isinstance(extra_params_raw, Mapping):
            raise ConfigError(
                "'source.auth.extra_params' must be a mapping when provided"
            )
        for key, value in extra_params_raw.items():
            extra_params[str(key)] = value

    return AuthConfig(
        type="oauth2",
        token_url=token_url.strip(),
        client_id=client_id.strip(),
        client_secret=client_secret,
        scope=scope,
        audience=audience,
        extra_params=extra_params,
        secret=auth_secret,
        uc_secret=auth_uc_secret,
    )


def _parse_stream(raw: Any) -> StreamConfig:
    if not isinstance(raw, dict):
        raise ConfigError("Each stream must be a mapping")

    path = raw.get("path")

    # Check if we're using endpoint partitioning
    partition_data = raw.get("partition", {})
    using_endpoint_partitioning = (
        isinstance(partition_data, dict)
        and partition_data.get("strategy") == "endpoints"
        and partition_data.get("endpoints")
    )

    # Only validate path if not using endpoint partitioning or if path is provided
    if path is None:
        if not using_endpoint_partitioning:
            raise ConfigError(
                "Stream 'path' is required unless using endpoint partitioning"
            )
        # Use a placeholder path that will be overridden by endpoint partitioning
        path = "/"
    elif not isinstance(path, str) or not path.startswith("/"):
        raise ConfigError("Stream 'path' must be an absolute path starting with '/'")

    # Derive name if not supplied
    raw_name = raw.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        name = raw_name.strip()
    else:
        # derive from path: strip leading '/', replace '/' with '_', fallback to 'stream'
        derived = path.lstrip("/").replace("/", "_") or "stream"
        name = derived

    params = raw.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ConfigError("Stream 'params' must be a mapping when provided")

    headers = raw.get("headers", {})
    if headers is None:
        headers = {}
    if not isinstance(headers, dict):
        raise ConfigError("Stream 'headers' must be a mapping when provided")

    pagination = _parse_pagination(raw.get("pagination"))
    incremental = _parse_incremental(raw.get("incremental"))
    record_selector = _parse_record_selector(raw.get("record_selector"))
    error_handler = _parse_error_handler(raw.get("error_handler"))
    partition = _parse_partition(raw.get("partition"))
    option_secrets = _parse_option_secrets(raw.get("option_secrets"))
    pushdown_params = _parse_pushdown_params(raw.get("pushdown_params"))

    infer_schema = raw.get("infer_schema")
    schema = raw.get("schema")
    if not infer_schema and not schema:
        # Default to true if neither is provided
        infer_schema = True
    if schema:
        if not isinstance(schema, str) or not schema.strip():
            raise ConfigError("'schema' must be a non-empty string when provided")
        try:
            _validate_ddl(schema)
        except Exception as e:
            raise ConfigError(f"Invalid schema DDL: {e}") from e

    resolved_params = {key: _coerce_env(value) for key, value in params.items()}
    resolved_headers = {key: _coerce_env(value) for key, value in headers.items()}

    streaming = bool(raw.get("streaming", False))

    response_format = raw.get("response_format", "json") or "json"
    if response_format not in {"json", "xml"}:
        raise ConfigError(f"Unsupported response_format: {response_format}")

    xml_record_path = _maybe_str(raw.get("xml_record_path"), "xml_record_path")

    if xml_record_path and response_format != "xml":
        raise ConfigError("'xml_record_path' requires 'response_format: xml'")
    if response_format == "xml" and not xml_record_path:
        raise ConfigError("'response_format: xml' requires 'xml_record_path' to be set")

    stream = StreamConfig(
        name=name,
        path=path,
        params=resolved_params,
        headers=resolved_headers,
        pagination=pagination,
        incremental=incremental,
        infer_schema=infer_schema,
        schema=schema,
        record_selector=record_selector,
        error_handler=error_handler,
        partition=partition,
        streaming=streaming,
        response_format=response_format,
        xml_record_path=xml_record_path,
        pushdown_params=pushdown_params,
        option_secrets=option_secrets,
    )
    _check_pushdown_collisions(stream)
    return stream


def _parse_pushdown_params(raw: Any) -> Dict[str, str]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ConfigError("'pushdown_params' must be a mapping when provided")
    result: Dict[str, str] = {}
    for column, param in raw.items():
        if not isinstance(column, str) or not column.strip():
            raise ConfigError("'pushdown_params' keys must be non-empty column names")
        if not isinstance(param, str) or not param.strip():
            raise ConfigError(
                f"'pushdown_params.{column}' must be a non-empty query parameter name"
            )
        result[column] = param
    return result


def _parse_pagination(raw: Any) -> PaginationConfig:
    if raw is None:
        return PaginationConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'pagination' must be a mapping when provided")

    pag_type = raw.get("type", "none")
    allowed_types = {"none", "link_header", "offset", "cursor", "page"}
    if pag_type not in allowed_types:
        raise ConfigError(f"Unsupported pagination type: {pag_type}")

    page_size = _maybe_int(raw.get("page_size"), "pagination.page_size", minimum=1)
    limit_param = _maybe_str(raw.get("limit_param"), "pagination.limit_param")
    offset_param = _maybe_str(raw.get("offset_param"), "pagination.offset_param")
    start_offset = _maybe_int(
        raw.get("start_offset"), "pagination.start_offset", minimum=0, default=0
    )
    page_param = _maybe_str(raw.get("page_param"), "pagination.page_param")
    start_page = _maybe_int(
        raw.get("start_page"), "pagination.start_page", minimum=1, default=1
    )
    cursor_param = _maybe_str(raw.get("cursor_param"), "pagination.cursor_param")
    cursor_path = _maybe_path(raw.get("cursor_path"), "pagination.cursor_path")
    next_url_path = _maybe_path(raw.get("next_url_path"), "pagination.next_url_path")
    cursor_header = _maybe_str(raw.get("cursor_header"), "pagination.cursor_header")
    initial_cursor = _maybe_str(raw.get("initial_cursor"), "pagination.initial_cursor")
    stop_on_empty = _maybe_bool(
        raw.get("stop_on_empty_response"),
        "pagination.stop_on_empty_response",
        default=True,
    )
    total_pages_path = _maybe_path(
        raw.get("total_pages_path"), "pagination.total_pages_path"
    )
    total_pages_header = _maybe_str(
        raw.get("total_pages_header"), "pagination.total_pages_header"
    )
    total_records_path = _maybe_path(
        raw.get("total_records_path"), "pagination.total_records_path"
    )
    total_records_header = _maybe_str(
        raw.get("total_records_header"), "pagination.total_records_header"
    )

    if pag_type == "offset":
        if offset_param is None:
            offset_param = "offset"
        if limit_param is None and page_size is not None:
            limit_param = "limit"
    if pag_type == "page":
        if page_param is None:
            page_param = "page"
        if limit_param is None and page_size is not None:
            limit_param = "per_page"
    if pag_type == "cursor":
        if not cursor_param and not next_url_path:
            raise ConfigError(
                "Cursor pagination requires either 'cursor_param' or 'next_url_path' to be set"
            )
        if cursor_param and not (cursor_path or cursor_header or initial_cursor):
            raise ConfigError(
                "When 'cursor_param' is provided you must supply one of 'cursor_path',"
                " 'cursor_header', or 'initial_cursor'"
            )

    return PaginationConfig(
        type=pag_type,
        page_size=page_size,
        limit_param=limit_param,
        offset_param=offset_param,
        start_offset=start_offset,
        page_param=page_param,
        start_page=start_page,
        cursor_param=cursor_param,
        cursor_path=cursor_path,
        next_url_path=next_url_path,
        cursor_header=cursor_header,
        initial_cursor=initial_cursor,
        stop_on_empty_response=stop_on_empty,
        total_pages_path=total_pages_path,
        total_pages_header=total_pages_header,
        total_records_path=total_records_path,
        total_records_header=total_records_header,
    )


def _pagination_to_dict(config: PaginationConfig) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"type": config.type}

    if config.page_size is not None:
        payload["page_size"] = config.page_size
    if config.limit_param:
        payload["limit_param"] = config.limit_param
    if config.offset_param and config.type == "offset":
        payload["offset_param"] = config.offset_param
    if config.start_offset and config.type == "offset":
        payload["start_offset"] = config.start_offset
    if config.page_param and config.type == "page":
        payload["page_param"] = config.page_param
    if config.start_page != 1 and config.type == "page":
        payload["start_page"] = config.start_page
    if config.cursor_param and config.type == "cursor":
        payload["cursor_param"] = config.cursor_param
    if config.cursor_path:
        payload["cursor_path"] = list(config.cursor_path)
    if config.next_url_path:
        payload["next_url_path"] = list(config.next_url_path)
    if config.cursor_header:
        payload["cursor_header"] = config.cursor_header
    if config.initial_cursor:
        payload["initial_cursor"] = config.initial_cursor
    if not config.stop_on_empty_response:
        payload["stop_on_empty_response"] = False
    if config.total_pages_path:
        payload["total_pages_path"] = list(config.total_pages_path)
    if config.total_pages_header:
        payload["total_pages_header"] = config.total_pages_header
    if config.total_records_path:
        payload["total_records_path"] = list(config.total_records_path)
    if config.total_records_header:
        payload["total_records_header"] = config.total_records_header

    return payload


def _maybe_int(
    value: Any,
    field: str,
    *,
    minimum: Optional[int] = None,
    default: Optional[int] = None,
) -> Optional[int]:
    if value is None:
        return default
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{field} must be an integer") from None
    if minimum is not None and result < minimum:
        raise ConfigError(f"{field} must be >= {minimum}")
    return result


def _maybe_str(value: Any, field: str) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ConfigError(f"{field} must be a non-empty string when provided")
    return value


def _maybe_path(value: Any, field: str) -> Tuple[str, ...]:
    if value in (None, [], ()):  # treat empty as no path
        return tuple()
    if isinstance(value, str):
        parts = [segment.strip() for segment in value.split(".") if segment.strip()]
        if not parts:
            raise ConfigError(f"{field} must not be empty")
        return tuple(parts)
    if isinstance(value, (list, tuple)):
        parts: List[str] = []
        for segment in value:
            if not isinstance(segment, str) or not segment:
                raise ConfigError(f"{field} entries must be non-empty strings")
            parts.append(segment)
        return tuple(parts)
    raise ConfigError(f"{field} must be a list of strings or dotted path")


def _maybe_bool(value: Any, field: str, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "y", "on"}:
            return True
        if lowered in {"false", "0", "no", "n", "off"}:
            return False
    if isinstance(value, (int, float)):
        return bool(value)
    raise ConfigError(f"{field} must be a boolean value")


def _parse_incremental(raw: Any) -> IncrementalConfig:
    if raw is None:
        return IncrementalConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'incremental' must be a mapping when provided")

    mode = raw.get("mode")
    cursor_param = raw.get("cursor_param")
    cursor_field = raw.get("cursor_field")
    start_value = raw.get("start_value")

    return IncrementalConfig(
        mode=str(mode) if mode else None,
        cursor_param=str(cursor_param) if cursor_param else None,
        cursor_field=str(cursor_field) if cursor_field else None,
        state_path=_maybe_str(raw.get("state_path"), "incremental.state_path"),
        start_value=str(start_value) if start_value not in (None, "") else None,
        state_key=_maybe_str(raw.get("state_key"), "incremental.state_key"),
    )


def _parse_record_selector(raw: Any) -> RecordSelectorConfig:
    if raw is None:
        return RecordSelectorConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'record_selector' must be a mapping when provided")

    field_path_raw = raw.get("field_path", [])
    if isinstance(field_path_raw, str):
        field_path = [field_path_raw]
    elif isinstance(field_path_raw, list):
        field_path = []
        for entry in field_path_raw:
            if not isinstance(entry, str) or not entry.strip():
                raise ConfigError(
                    "Each entry in 'record_selector.field_path' must be a non-empty string"
                )
            field_path.append(entry.strip())
    else:
        raise ConfigError(
            "'record_selector.field_path' must be a list of strings or a string"
        )

    record_filter = raw.get("record_filter")
    if record_filter is not None:
        if not isinstance(record_filter, str) or not record_filter.strip():
            raise ConfigError(
                "'record_selector.record_filter' must be a non-empty string when provided"
            )
        record_filter = record_filter.strip()

    cast_to_schema_types = bool(raw.get("cast_to_schema_types", False))

    return RecordSelectorConfig(
        field_path=field_path,
        record_filter=record_filter,
        cast_to_schema_types=cast_to_schema_types,
    )


def _parse_error_handler(raw: Any) -> ErrorHandlerConfig:
    if raw is None:
        return ErrorHandlerConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'error_handler' must be a mapping when provided")

    max_retries = raw.get("max_retries", 5)
    if not isinstance(max_retries, int) or max_retries < 0:
        raise ConfigError("'error_handler.max_retries' must be a non-negative integer")

    retry_statuses_raw = raw.get("retry_statuses")
    if retry_statuses_raw is None:
        retry_statuses = _default_retry_statuses()
    else:
        if not isinstance(retry_statuses_raw, list):
            raise ConfigError(
                "'error_handler.retry_statuses' must be a list when provided"
            )
        retry_statuses = tuple(
            _normalize_status_spec(value) for value in retry_statuses_raw
        )

    retry_on_timeout = raw.get("retry_on_timeout", True)
    if not isinstance(retry_on_timeout, bool):
        raise ConfigError(
            "'error_handler.retry_on_timeout' must be a boolean when provided"
        )

    retry_on_connection_errors = raw.get("retry_on_connection_errors", True)
    if not isinstance(retry_on_connection_errors, bool):
        raise ConfigError(
            "'error_handler.retry_on_connection_errors' must be a boolean when provided"
        )

    backoff_raw = raw.get("backoff")
    if backoff_raw is None:
        backoff = BackoffConfig()
    else:
        if not isinstance(backoff_raw, dict):
            raise ConfigError("'error_handler.backoff' must be a mapping when provided")

        defaults = BackoffConfig()
        initial = _ensure_non_negative_float(
            backoff_raw.get("initial_delay_seconds", defaults.initial_delay_seconds),
            "error_handler.backoff.initial_delay_seconds",
        )
        max_delay = _ensure_non_negative_float(
            backoff_raw.get("max_delay_seconds", defaults.max_delay_seconds),
            "error_handler.backoff.max_delay_seconds",
        )
        multiplier = _ensure_positive_float(
            backoff_raw.get("multiplier", defaults.multiplier),
            "error_handler.backoff.multiplier",
        )

        if max_delay and max_delay < initial:
            raise ConfigError(
                "'error_handler.backoff.max_delay_seconds' must be greater than or equal to initial_delay_seconds"
            )

        backoff = BackoffConfig(
            initial_delay_seconds=initial,
            max_delay_seconds=max_delay,
            multiplier=multiplier,
        )

    return ErrorHandlerConfig(
        max_retries=max_retries,
        retry_statuses=retry_statuses,
        retry_on_timeout=retry_on_timeout,
        retry_on_connection_errors=retry_on_connection_errors,
        backoff=backoff,
    )


def _parse_partition(raw: Any) -> PartitionConfig:
    """Parse the partition configuration from a raw config dict."""
    if raw is None:
        return PartitionConfig()

    if not isinstance(raw, dict):
        raise ConfigError("'partition' must be a mapping when provided")

    strategy = raw.get("strategy", "none")
    allowed_strategies = {"none", "pagination", "param_range", "endpoints"}
    if strategy not in allowed_strategies:
        raise ConfigError(f"Unsupported partition strategy: {strategy}")

    # Default values
    param = None
    values = None
    range_start = None
    range_end = None
    range_step = None
    range_kind = None
    value_template = None
    extra_template = None
    endpoints = ()

    # Strategy-specific validation and parsing
    if strategy == "param_range":
        param = _maybe_str(raw.get("param"), "partition.param")
        if not param:
            raise ConfigError(
                "'partition.param' must be provided for param_range strategy"
            )

        def _normalize_range_kind(
            value: Any, *, default: Optional[str] = None
        ) -> Optional[str]:
            if value is None:
                return default
            text = str(value).strip().lower()
            if not text:
                return default
            if text not in {"numeric", "date"}:
                raise ConfigError(
                    "'partition.range_kind' must be either 'numeric' or 'date'"
                )
            return "date" if text == "date" else "numeric"

        def _normalize_range_step(value: Any) -> Optional[int]:
            if value is None:
                return None
            try:
                result = int(value)
            except (TypeError, ValueError):
                raise ConfigError(
                    "'partition.range_step' must be a positive integer"
                ) from None
            if result <= 0:
                raise ConfigError("'partition.range_step' must be a positive integer")
            return result

        raw_values = raw.get("values")
        if isinstance(raw_values, (list, tuple)):
            cleaned_values = [
                str(item).strip() for item in raw_values if str(item).strip()
            ]
            values = tuple(cleaned_values) if cleaned_values else None
        elif raw_values is not None:
            text = str(raw_values).strip()
            values = text or None

        range_start = raw.get("range_start")
        range_end = raw.get("range_end")
        if values is None:
            if range_start is None or range_end is None:
                raise ConfigError(
                    "param_range partition requires either 'values' or both 'range_start' and 'range_end'"
                )
            range_kind = _normalize_range_kind(
                raw.get("range_kind", "numeric"), default="numeric"
            )
            range_step = _normalize_range_step(raw.get("range_step"))
        else:
            if (range_start is None) ^ (range_end is None):
                raise ConfigError(
                    "Provide both 'partition.range_start' and 'partition.range_end' when defining a range"
                )
            range_kind = _normalize_range_kind(raw.get("range_kind"))
            range_step = _normalize_range_step(raw.get("range_step"))

        value_template = _maybe_str(
            raw.get("value_template"), "partition.value_template"
        )
        extra_template = _maybe_str(
            raw.get("extra_template"), "partition.extra_template"
        )

    elif strategy == "endpoints":
        raw_endpoints = raw.get("endpoints")
        if not raw_endpoints:
            raise ConfigError(
                "'partition.endpoints' must be provided for endpoints strategy"
            )

        if isinstance(raw_endpoints, str):
            # Handle comma-separated string format
            endpoint_list = [e.strip() for e in raw_endpoints.split(",") if e.strip()]
            if not endpoint_list:
                raise ConfigError("'partition.endpoints' must not be empty")
            endpoints = tuple(endpoint_list)
        elif isinstance(raw_endpoints, (list, tuple)):
            # Handle array format
            endpoint_list = []
            for endpoint in raw_endpoints:
                if not isinstance(endpoint, str) or not endpoint.strip():
                    raise ConfigError(
                        "Each endpoint in 'partition.endpoints' must be a non-empty string"
                    )
                endpoint_list.append(endpoint.strip())
            endpoints = tuple(endpoint_list)
        else:
            raise ConfigError(
                "'partition.endpoints' must be a list of strings or a comma-separated string"
            )

    return PartitionConfig(
        strategy=strategy,
        param=param,
        values=values,
        range_start=range_start,
        range_end=range_end,
        range_step=range_step,
        range_kind=range_kind,
        value_template=value_template,
        extra_template=extra_template,
        endpoints=endpoints,
    )


def _normalize_status_spec(value: Any) -> str:
    if isinstance(value, int):
        code = value
        if code < 100 or code > 599:
            raise ConfigError("HTTP status codes must be between 100 and 599")
        return str(code)

    if isinstance(value, str):
        text = value.strip().upper()
        if not text:
            raise ConfigError("HTTP status code entries cannot be empty")
        if text.endswith("XX"):
            if len(text) != 3 or not text[0].isdigit():
                raise ConfigError("Pattern status codes must look like '5XX'")
            bucket = int(text[0])
            if bucket < 1 or bucket > 5:
                raise ConfigError(
                    "Pattern status codes must be between '1XX' and '5XX'"
                )
            return f"{bucket}XX"
        if text.isdigit():
            code = int(text)
            if code < 100 or code > 599:
                raise ConfigError("HTTP status codes must be between 100 and 599")
            return str(code)
        raise ConfigError("Status codes must be integers or patterns like '5XX'")

    raise ConfigError("Status codes must be integers or strings")


def _ensure_non_negative_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"'{field_name}' must be a number")
    if not isinstance(value, (int, float)):
        raise ConfigError(f"'{field_name}' must be a number")
    result = float(value)
    if result < 0:
        raise ConfigError(f"'{field_name}' must be greater than or equal to 0")
    return result


def _ensure_positive_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"'{field_name}' must be a number")
    if not isinstance(value, (int, float)):
        raise ConfigError(f"'{field_name}' must be a number")
    result = float(value)
    if result <= 0:
        raise ConfigError(f"'{field_name}' must be greater than 0")
    return result


def _validate_ddl(ddl: str) -> None:
    """Validate schema DDL syntax without requiring pyspark to be installed.

    This runs during `parse_config` for every stream with a `schema`, which
    means it runs during `generate()` too. pyspark is only in the `builder`
    extra, so this must not import it (see `_validate_ddl_syntax`).
    """
    _validate_ddl_syntax(ddl)


def parse_schema_struct(schema_text: str) -> "StructType":
    """Parse a Spark SQL DDL string into a real pyspark StructType.

    Requires pyspark to be installed (it's a lazy, local import below since
    pyspark is optional at generation time). Not used by config parsing or
    codegen — those only need `_validate_ddl_syntax`'s pyspark-free check.
    """
    from pyspark.sql.types import StructType

    try:
        return StructType.fromDDL(schema_text)
    except Exception as original_exc:  # pragma: no cover - requires Spark
        try:
            return _parse_ddl_without_spark(schema_text)
        except Exception as fallback_exc:
            raise ValueError(
                f"Unable to parse schema: {fallback_exc}"
            ) from original_exc


def _validate_ddl_syntax(schema_text: str) -> None:
    """Check a schema DDL string is well-formed, without pyspark.

    Supports the same grammar Spark's DDL parser does: flat `name TYPE`
    pairs, `DECIMAL(p,s)`, nested `ARRAY<T>` / `MAP<K,V>` / `STRUCT<...>`
    (recursively, to any depth), and backtick-quoted field names — at the
    top level and inside a STRUCT. Never constructs Spark type objects, so
    it has no pyspark dependency at all.
    """
    if not schema_text or not schema_text.strip():
        raise ValueError("Schema definition is empty")

    field_defs = _split_top_level(schema_text)
    if not field_defs:
        raise ValueError("Schema definition has no fields")

    for field_def in field_defs:
        _, type_spec = _split_field_name(field_def)
        type_spec = type_spec.strip()
        if not type_spec:
            raise ValueError(f"Invalid field definition: '{field_def}'")
        _validate_type_expr(type_spec)


def _split_field_name(field_def: str) -> Tuple[str, str]:
    """Split `` `name` REST `` or `name REST` into (name, rest).

    `rest` is returned unstripped/unmodified after the name (it may still
    have a leading `:` for the STRUCT inner `name: TYPE` syntax, which the
    caller is responsible for stripping).
    """
    text = field_def.strip()
    if not text:
        raise ValueError("Invalid field definition: ''")

    if text.startswith("`"):
        end = text.find("`", 1)
        if end == -1:
            raise ValueError(f"Unterminated backtick-quoted name in '{field_def}'")
        name = text[1:end]
        if not name:
            raise ValueError(f"Empty backtick-quoted name in '{field_def}'")
        return name, text[end + 1 :]

    # Stop at the first whitespace OR ':' — the latter so a STRUCT inner
    # field's `name: TYPE` syntax splits the name off cleanly too (a bare
    # top-level field never legitimately has a ':' right after its name,
    # so this doesn't change top-level parsing).
    match = re.match(r"^([^\s:]+)(.*)$", text, re.DOTALL)
    if not match:
        raise ValueError(f"Invalid field definition: '{field_def}'")
    return match.group(1), match.group(2)


def _extract_angle_content(type_spec: str, keyword: str) -> str:
    """Return the text between the outer `<` and `>` of `KEYWORD<...>`.

    Requires the outer brackets to wrap the *entire* remainder of
    `type_spec` (no trailing text after the matching `>`), and to be
    balanced with respect to nested `<`/`>` and backtick-quoted spans.
    """
    stripped = type_spec.strip()
    match = re.match(rf"^{keyword}\s*<", stripped, re.IGNORECASE)
    if not match or not stripped.endswith(">"):
        raise ValueError(f"Malformed {keyword.upper()} type: '{type_spec}'")

    body = stripped[match.end() - 1 :]  # starts at the opening '<'
    depth = 0
    in_backtick = False
    for index, ch in enumerate(body):
        if ch == "`":
            in_backtick = not in_backtick
            continue
        if in_backtick:
            continue
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
            if depth < 0:
                raise ValueError(f"Unbalanced brackets in type: '{type_spec}'")
            if depth == 0 and index != len(body) - 1:
                raise ValueError(f"Malformed {keyword.upper()} type: '{type_spec}'")
    if depth != 0 or in_backtick:
        raise ValueError(f"Unbalanced brackets in type: '{type_spec}'")

    return body[1:-1]


_NESTED_TYPE_RE = re.compile(r"^(array|map|struct)\s*<", re.IGNORECASE)


def _validate_type_expr(type_spec: str) -> None:
    """Validate a single type expression, recursing into nested types.

    pyspark-free: scalars go to `_validate_simple_type`; ARRAY/MAP/STRUCT
    are unwrapped and their inner type expression(s)/fields are validated
    recursively via this same function.
    """
    normalized = type_spec.strip()
    if not normalized:
        raise ValueError("Type expression is empty")

    match = _NESTED_TYPE_RE.match(normalized)
    if not match:
        _validate_simple_type(normalized)
        return

    keyword = match.group(1).lower()

    if keyword == "array":
        content = _extract_angle_content(normalized, "array").strip()
        if not content:
            raise ValueError(f"ARRAY type must have an element type: '{type_spec}'")
        _validate_type_expr(content)
        return

    if keyword == "map":
        content = _extract_angle_content(normalized, "map")
        parts = _split_top_level(content)
        if len(parts) != 2:
            raise ValueError(
                f"MAP type requires exactly a key type and a value type: '{type_spec}'"
            )
        _validate_type_expr(parts[0])
        _validate_type_expr(parts[1])
        return

    # keyword == "struct"
    # An empty STRUCT<> is unusual but real Spark (StructType.fromDDL)
    # accepts it as a zero-field struct, so the validator must too.
    content = _extract_angle_content(normalized, "struct")
    inner_fields = _split_top_level(content)
    for inner_field in inner_fields:
        _validate_struct_field(inner_field)


def _validate_struct_field(field_def: str) -> None:
    """Validate one `name: TYPE` or `name TYPE` field inside STRUCT<...>."""
    name, rest = _split_field_name(field_def)
    if not name:
        raise ValueError(f"Invalid STRUCT field: '{field_def}'")
    rest = rest.strip()
    if rest.startswith(":"):
        rest = rest[1:].strip()
    if not rest:
        raise ValueError(f"STRUCT field '{name}' is missing a type")
    _validate_type_expr(rest)


def _coerce_env(value: Any) -> Any:
    if isinstance(value, str) and value.startswith("${env:") and value.endswith("}"):
        env_var = value[len("${env:") : -1]
        return _resolve_env(env_var)
    if isinstance(value, list):
        return [_coerce_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _coerce_env(item) for key, item in value.items()}
    return value


def _resolve_env(name: str) -> str:
    from os import getenv

    resolved = getenv(name)
    if resolved is None:
        raise ConfigError(f"Environment variable '{name}' is not set")
    return resolved


def _parse_ddl_without_spark(schema_text: str) -> "StructType":
    # Local import: only reached from `parse_schema_struct`, which has
    # already imported pyspark lazily by the time this runs.
    from pyspark.sql.types import StructField, StructType

    if not schema_text or not schema_text.strip():
        raise ValueError("Schema definition is empty")

    field_defs = _split_top_level(schema_text)
    if not field_defs:
        raise ValueError("Schema definition has no fields")

    fields: List[StructField] = []
    for field_def in field_defs:
        parts = field_def.split(None, 1)
        if len(parts) < 2:
            raise ValueError(f"Invalid field definition: '{field_def}'")
        name, type_spec = parts[0], parts[1].strip()
        data_type = _parse_simple_type(type_spec)
        fields.append(StructField(name, data_type, nullable=True))

    return StructType(fields)


def _split_top_level(schema_text: str) -> List[str]:
    """Split on commas outside `<...>`/`(...)` nesting and outside backticks.

    A comma (or bracket) inside a backtick-quoted identifier — e.g.
    `` `weird,name` INT `` — must not affect splitting or depth tracking.
    """
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    in_backtick = False
    for ch in schema_text:
        if ch == "`":
            in_backtick = not in_backtick
            current.append(ch)
            continue
        if not in_backtick:
            if ch == "<" or ch == "(":
                depth += 1
            elif ch == ">" or ch == ")":
                depth = max(0, depth - 1)
            elif ch == "," and depth == 0:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                continue
        current.append(ch)

    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return parts


_DECIMAL_PATTERN = re.compile(r"decimal\s*\((\d+)\s*,\s*(\d+)\)", re.IGNORECASE)


_SIMPLE_TYPE_NAMES = {
    "string",
    "varchar",
    "char",
    "text",
    "boolean",
    "bool",
    "double",
    "float64",
    "float",
    "real",
    "tinyint",
    "smallint",
    "int",
    "integer",
    "bigint",
    "long",
    "timestamp",
    "date",
    "variant",
}


def _validate_simple_type(type_spec: str) -> None:
    """Check a single DDL field's type expression is recognized.

    pyspark-free counterpart to `_parse_simple_type`: validates the same
    grammar without constructing any Spark type object.
    """
    normalized = type_spec.strip().lower()

    if normalized.startswith("decimal") or normalized.startswith("numeric"):
        return  # with or without explicit (precision, scale)

    if normalized in _SIMPLE_TYPE_NAMES:
        return

    raise ValueError(f"Unsupported type expression '{type_spec}'")


def _parse_simple_type(type_spec: str):
    # Local import: only reached from `_parse_ddl_without_spark`, which is
    # only reached from `parse_schema_struct` after pyspark is confirmed
    # importable.
    from pyspark.sql.types import (
        BooleanType,
        ByteType,
        DateType,
        DecimalType,
        DoubleType,
        FloatType,
        IntegerType,
        LongType,
        ShortType,
        StringType,
        TimestampType,
        VariantType,
    )

    normalized = type_spec.strip().lower()

    if normalized.startswith("decimal") or normalized.startswith("numeric"):
        match = _DECIMAL_PATTERN.search(normalized)
        if match:
            precision = int(match.group(1))
            scale = int(match.group(2))
            return DecimalType(precision, scale)
        return DecimalType(38, 18)

    if normalized in {"string", "varchar", "char", "text"}:
        return StringType()
    if normalized in {"boolean", "bool"}:
        return BooleanType()
    if normalized in {"double", "float64"}:
        return DoubleType()
    if normalized in {"float", "real"}:
        return FloatType()
    if normalized in {"tinyint"}:
        return ByteType()
    if normalized in {"smallint"}:
        return ShortType()
    if normalized in {"int", "integer"}:
        return IntegerType()
    if normalized in {"bigint", "long"}:
        return LongType()
    if normalized == "timestamp":
        return TimestampType()
    if normalized == "date":
        return DateType()
    if normalized == "variant":
        return VariantType()

    raise ValueError(f"Unsupported type expression '{type_spec}'")
