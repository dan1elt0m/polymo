"""Configuration loading and validation for REST-backed data sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Mapping, Tuple
import re

import yaml
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
    StructField,
    StructType,
    TimestampType,
    VariantType,
)


class ConfigError(ValueError):
    """Raised when the user-provided YAML configuration is invalid."""


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration for REST requests."""

    type: Literal["none", "bearer", "oauth2"] = "none"
    token: str | None = None
    token_url: str | None = None
    client_id: str | None = None
    client_secret: str | None = None
    scope: Tuple[str, ...] = field(default_factory=tuple)
    audience: str | None = None
    extra_params: Mapping[str, Any] = field(default_factory=dict)


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
    """Incremental loading hints for future extensions."""

    mode: Optional[str] = None
    cursor_param: Optional[str] = None
    cursor_field: Optional[str] = None


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
    values: Optional[str] = None
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


@dataclass(frozen=True)
class RestSourceConfig:
    """Top-level configuration mapping for the connector."""

    version: str
    base_url: str
    auth: AuthConfig
    stream: StreamConfig
    options: Dict[str, Any] = field(default_factory=dict)


def load_config(
    path: str | Path,
    token: str | None = None,
    options: Optional[Mapping[str, Any]] = None,
) -> RestSourceConfig:
    """Load and validate a REST source configuration from YAML.

    Authentication details (token) are supplied separately and are NOT part of the YAML.
    """

    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text())
    return parse_config(raw, token=token, options=options)


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

    return RestSourceConfig(
        version=version,
        base_url=base_url.rstrip("/"),
        auth=auth,
        stream=stream,
        options=runtime_options,
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
        source["auth"] = auth_block

    stream = config.stream
    stream_dict: Dict[str, Any] = {
        # 'name' intentionally omitted from external representation
        "path": stream.path,
        "infer_schema": stream.infer_schema,
        "schema": stream.schema,
        "pagination": _pagination_to_dict(stream.pagination),
    }

    if stream.params:
        stream_dict["params"] = dict(stream.params)

    if stream.headers:
        stream_dict["headers"] = dict(stream.headers)

    # Always include incremental object, even if all fields are null
    incremental: Dict[str, Any] = {
        "mode": stream.incremental.mode,
        "cursor_param": stream.incremental.cursor_param,
        "cursor_field": stream.incremental.cursor_field,
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
    stream_dict["partition"] = {
        "strategy": partition.strategy,
        "param": partition.param,
        "values": partition.values,
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


def dump_config(config: RestSourceConfig) -> str:
    """Render a configuration as canonical YAML.

    Auth is intentionally stripped to avoid persisting secrets or auth type in YAML.
    """

    data = config_to_dict(config)
    data["source"].pop("auth", None)
    return yaml.safe_dump(data, sort_keys=False)


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
    if auth_type not in {"none", "bearer", "oauth2"}:
        raise ConfigError(f"Unsupported auth type: {auth_type}")

    if auth_type == "none":
        return AuthConfig()

    if auth_type == "bearer":
        raw_token = raw_auth.get("token")
        raw_token = raw_token.strip() if isinstance(raw_token, str) else None
        token = token_value or raw_token
        if not token:
            raise ConfigError(
                "Bearer auth requires a token supplied via config or runtime options"
            )
        return AuthConfig(type="bearer", token=token)

    # OAuth2 client credentials
    token_url = raw_auth.get("token_url")
    if not isinstance(token_url, str) or not token_url.strip():
        raise ConfigError("'source.auth.token_url' must be provided for oauth2 auth")

    client_id = raw_auth.get("client_id")
    if not isinstance(client_id, str) or not client_id.strip():
        raise ConfigError("'source.auth.client_id' must be provided for oauth2 auth")

    client_secret = raw_auth.get("client_secret")
    if isinstance(client_secret, str):
        client_secret = client_secret.strip() or None
        if (
            client_secret
            and client_secret.startswith("{{")
            and client_secret.endswith("}}")
        ):
            client_secret = None
    elif client_secret is not None:
        client_secret = str(client_secret)

    secret_from_options = runtime_options.pop("oauth_client_secret", None)
    if isinstance(secret_from_options, str):
        secret_from_options = secret_from_options.strip() or None
    elif secret_from_options is not None:
        secret_from_options = str(secret_from_options)

    client_secret = client_secret or token_value or secret_from_options
    if not client_secret:
        raise ConfigError(
            "OAuth2 auth requires a client secret supplied via config ('client_secret') or runtime option 'oauth_client_secret'",
        )

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

    return StreamConfig(
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
    )


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

    return IncrementalConfig(
        mode=str(mode) if mode else None,
        cursor_param=str(cursor_param) if cursor_param else None,
        cursor_field=str(cursor_field) if cursor_field else None,
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

        range_start = raw.get("range_start")
        range_end = raw.get("range_end")

        if range_start is None:
            raise ConfigError(
                "'partition.range_start' must be provided for param_range strategy"
            )
        if range_end is None:
            raise ConfigError(
                "'partition.range_end' must be provided for param_range strategy"
            )

        range_kind = raw.get("range_kind", "numeric")
        if range_kind not in {"numeric", "date"}:
            raise ConfigError(
                "'partition.range_kind' must be either 'numeric' or 'date'"
            )

        # Parse step if provided
        if "range_step" in raw:
            step_value = raw.get("range_step")
            if not isinstance(step_value, int) or step_value <= 0:
                raise ConfigError("'partition.range_step' must be a positive integer")
            range_step = step_value

        # Optional templates
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
    """Validate schema DDL without requiring a running Spark session."""
    parse_schema_struct(ddl)


def parse_schema_struct(schema_text: str) -> StructType:
    """Parse a Spark SQL DDL string into a StructType without needing Spark."""

    try:
        return StructType.fromDDL(schema_text)
    except Exception as original_exc:  # pragma: no cover - requires Spark
        try:
            return _parse_ddl_without_spark(schema_text)
        except Exception as fallback_exc:
            raise ValueError(
                f"Unable to parse schema: {fallback_exc}"
            ) from original_exc


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


def _parse_ddl_without_spark(schema_text: str) -> StructType:
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
    parts: List[str] = []
    current: List[str] = []
    depth = 0
    for ch in schema_text:
        if ch == "<" or ch == "(":
            depth += 1
        elif ch == ">" or ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
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


def _parse_simple_type(type_spec: str):
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
