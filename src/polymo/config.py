"""Configuration loading and validation for REST-backed data sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Mapping
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
)


class ConfigError(ValueError):
    """Raised when the user-provided YAML configuration is invalid."""


@dataclass(frozen=True)
class AuthConfig:
    """Authentication configuration for REST requests."""

    type: Literal["none", "bearer"] = "none"
    token: str | None = None


@dataclass(frozen=True)
class PaginationConfig:
    """Pagination strategy definition."""

    type: Literal["none", "link_header"] = "none"


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

    # token decides.
    if token:
        auth = AuthConfig(type="bearer", token=token)
    else:
        auth = AuthConfig()

    base_url = source.get("base_url")
    if not isinstance(base_url, str) or not base_url:
        raise ConfigError("'source.base_url' must be a non-empty string")

    # Only support single stream format
    stream_raw = raw.get("stream")
    if not stream_raw:
        raise ConfigError("A stream must be defined")

    stream = _parse_stream(stream_raw)

    runtime_options = dict(options or {})

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
        source["auth"] = {"type": config.auth.type}

    stream = config.stream
    stream_dict: Dict[str, Any] = {
        # 'name' intentionally omitted from external representation
        "path": stream.path,
        "infer_schema": stream.infer_schema,
        "schema": stream.schema,
        "pagination": {"type": stream.pagination.type},
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


def _parse_auth(auth: dict) -> AuthConfig:  # Deprecated – retained for backward compatibility (unused)
    token = auth.get("token")
    auth_type = auth.get("type")
    if auth_type == "bearer":
        if not isinstance(token, str):
            raise ConfigError("'token' must be a string")
        if token == "":
            raise ConfigError("'token' cannot be empty")
    return AuthConfig(type=auth_type, token=token)


def _parse_stream(raw: Any) -> StreamConfig:
    if not isinstance(raw, dict):
        raise ConfigError("Each stream must be a mapping")

    path = raw.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
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
    )


def _parse_pagination(raw: Any) -> PaginationConfig:
    if raw is None:
        return PaginationConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'pagination' must be a mapping when provided")

    pag_type = raw.get("type", "none")
    if pag_type not in {"none", "link_header"}:
        raise ConfigError(f"Unsupported pagination type: {pag_type}")

    return PaginationConfig(type=pag_type)


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
                raise ConfigError("Each entry in 'record_selector.field_path' must be a non-empty string")
            field_path.append(entry.strip())
    else:
        raise ConfigError("'record_selector.field_path' must be a list of strings or a string")

    record_filter = raw.get("record_filter")
    if record_filter is not None:
        if not isinstance(record_filter, str) or not record_filter.strip():
            raise ConfigError("'record_selector.record_filter' must be a non-empty string when provided")
        record_filter = record_filter.strip()

    cast_to_schema_types = bool(raw.get("cast_to_schema_types", False))

    return RecordSelectorConfig(
        field_path=field_path,
        record_filter=record_filter,
        cast_to_schema_types=cast_to_schema_types,
    )


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
            raise ValueError(f"Unable to parse schema: {fallback_exc}") from original_exc

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

    raise ValueError(f"Unsupported type expression '{type_spec}' without Spark runtime")
