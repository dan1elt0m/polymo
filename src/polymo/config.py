"""Configuration loading and validation for REST-backed data sources."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pyspark.sql.types import StructType


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
class StreamConfig:
    """Definition of a logical stream within the REST connector."""

    name: str
    path: str
    params: Dict[str, Any] = field(default_factory=dict)
    pagination: PaginationConfig = field(default_factory=PaginationConfig)
    incremental: IncrementalConfig = field(default_factory=IncrementalConfig)
    infer_schema: bool = True
    schema: str | None = None


@dataclass(frozen=True)
class RestSourceConfig:
    """Top-level configuration mapping for the connector."""

    version: str
    base_url: str
    auth: AuthConfig
    stream: StreamConfig


def load_config(path: str | Path, token: str) -> RestSourceConfig:
    """Load and validate a REST source configuration from YAML."""

    config_path = Path(path)
    if not config_path.exists():
        raise ConfigError(f"Configuration file not found: {config_path}")

    raw = yaml.safe_load(config_path.read_text())
    return parse_config(raw, token)


def parse_config(raw: Any, token: str = None) -> RestSourceConfig:
    """Validate a configuration object previously parsed from YAML."""

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

    auth = _parse_auth(source.get("auth", AuthConfig()))
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
    )


def config_to_dict(config: RestSourceConfig) -> Dict[str, Any]:
    """Convert a RestSourceConfig instance into a canonical plain dict."""

    source: Dict[str, Any] = {
        "type": "rest",
        "base_url": config.base_url,
    }

    auth: Dict[str, Any] = {"type": config.auth.type}
    if config.auth.type == "bearer" :
        source["auth"] = auth

    stream = config.stream
    stream_dict: Dict[str, Any] = {
        "name": stream.name,
        "path": stream.path,
        "infer_schema": stream.infer_schema,
        "schema": stream.schema,
        "pagination": {"type": stream.pagination.type},
    }

    if stream.params:
        stream_dict["params"] = dict(stream.params)

    # Always include incremental object, even if all fields are null
    incremental: Dict[str, Any] = {
        "mode": stream.incremental.mode,
        "cursor_param": stream.incremental.cursor_param,
        "cursor_field": stream.incremental.cursor_field,
    }
    stream_dict["incremental"] = incremental

    return {
        "version": config.version,
        "source": source,
        "stream": stream_dict,
    }


def dump_config(config: RestSourceConfig) -> str:
    """Render a configuration as canonical YAML."""

    return yaml.safe_dump(config_to_dict(config), sort_keys=False)


def _parse_auth(auth: AuthConfig) -> AuthConfig:
    if auth.token is None:
        return AuthConfig()
    if not isinstance(auth.token, str):
        raise ConfigError("'token' must be a string")
    auth_type = "bearer" if auth.token else "none"
    return AuthConfig(type=auth_type, token=auth.token)


def _parse_stream(raw: Any) -> StreamConfig:
    if not isinstance(raw, dict):
        raise ConfigError("Each stream must be a mapping")

    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ConfigError("Stream 'name' must be a non-empty string")

    path = raw.get("path")
    if not isinstance(path, str) or not path.startswith("/"):
        raise ConfigError("Stream 'path' must be an absolute path starting with '/'")

    params = raw.get("params", {})
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ConfigError("Stream 'params' must be a mapping when provided")

    pagination = _parse_pagination(raw.get("pagination"))
    incremental = _parse_incremental(raw.get("incremental"))
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

    return StreamConfig(
        name=name,
        path=path,
        params=resolved_params,
        pagination=pagination,
        incremental=incremental,
        infer_schema=infer_schema,
        schema=schema,
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


def _validate_ddl(ddl) -> Any:
    """Get or create a Spark session."""
    from pyspark.sql import SparkSession

    SparkSession.builder \
        .appName("polymo") \
        .getOrCreate()
    StructType.fromDDL(ddl)

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
