"""Pydantic models that mirror the Polymo REST configuration schema."""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence

import yaml
from pydantic import BaseModel, ConfigDict, Field

from .config import (
    ConfigError,
    RestSourceConfig,
    config_to_dict,
    dump_config,
    parse_config,
)


class AuthModel(BaseModel):
    """Authentication settings for the REST source."""

    type: str = Field(
        "none", description="Authentication strategy ('none', 'bearer', or 'oauth2')."
    )
    token: Optional[str] = Field(
        default=None,
        description="Static bearer token supplied directly in the config (rare, use runtime tokens instead).",
    )
    token_url: Optional[str] = Field(
        default=None,
        description="OAuth2 token endpoint used for client-credentials flows (required for oauth2).",
    )
    client_id: Optional[str] = Field(
        default=None, description="OAuth2 client identifier (required for oauth2)."
    )
    client_secret: Optional[str] = Field(
        default=None,
        description="Optional OAuth2 client secret embedded in the config (use runtime secrets when possible).",
    )
    scope: Optional[List[str]] = Field(
        default=None,
        description="Scopes requested during OAuth2 token exchange (list of strings).",
    )
    audience: Optional[str] = Field(
        default=None, description="Optional OAuth2 audience parameter."
    )
    extra_params: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional key/value pairs merged into the OAuth2 token request payload.",
    )

    model_config = ConfigDict(populate_by_name=True)


class PaginationModel(BaseModel):
    """Pagination configuration mirroring the YAML contract."""

    type: str = Field("none", description="Pagination strategy type.")
    page_size: Optional[int] = Field(
        default=None, description="Number of records requested per page."
    )
    limit_param: Optional[str] = Field(
        default=None, description="Query parameter controlling page size."
    )
    offset_param: Optional[str] = Field(
        default=None, description="Query parameter incremented for offset pagination."
    )
    start_offset: Optional[int] = Field(
        default=None, description="Initial offset value for offset pagination."
    )
    page_param: Optional[str] = Field(
        default=None, description="Query parameter incremented for page pagination."
    )
    start_page: Optional[int] = Field(
        default=None, description="Initial page number for page pagination."
    )
    cursor_param: Optional[str] = Field(
        default=None, description="Query parameter used to send the cursor value."
    )
    cursor_path: Optional[List[str]] = Field(
        default=None, description="JSON path extracting the next cursor from a payload."
    )
    next_url_path: Optional[List[str]] = Field(
        default=None,
        description="JSON path pointing to the next page URL in the payload.",
    )
    cursor_header: Optional[str] = Field(
        default=None, description="HTTP response header containing the next cursor."
    )
    initial_cursor: Optional[str] = Field(
        default=None, description="Cursor value supplied for the very first request."
    )
    stop_on_empty_response: Optional[bool] = Field(
        default=None, description="Stop pagination when the API returns an empty page."
    )
    total_pages_path: Optional[List[str]] = Field(
        default=None, description="JSON path pointing to the total number of pages."
    )
    total_pages_header: Optional[str] = Field(
        default=None, description="HTTP header containing the total number of pages."
    )
    total_records_path: Optional[List[str]] = Field(
        default=None, description="JSON path pointing to the total number of records."
    )
    total_records_header: Optional[str] = Field(
        default=None, description="HTTP header containing the total number of records."
    )

    model_config = ConfigDict(populate_by_name=True)


class IncrementalModel(BaseModel):
    """Incremental cursor settings."""

    mode: Optional[str] = Field(
        default=None, description="Incremental sync mode (reserved for future use)."
    )
    cursor_param: Optional[str] = Field(
        default=None, description="Request parameter used to send the cursor value."
    )
    cursor_field: Optional[str] = Field(
        default=None, description="Field inside each record holding the cursor value."
    )


class BackoffModel(BaseModel):
    """Retry backoff strategy."""

    initial_delay_seconds: float = Field(
        1.0, description="Initial delay in seconds before performing the first retry."
    )
    max_delay_seconds: float = Field(
        30.0, description="Maximum delay in seconds between retries."
    )
    multiplier: float = Field(
        2.0, description="Exponential multiplier applied to the delay after each retry."
    )


class ErrorHandlerModel(BaseModel):
    """Error handling configuration."""

    max_retries: int = Field(5, description="Maximum number of retries before failing.")
    retry_statuses: List[str] = Field(
        default_factory=lambda: ["5XX", "429"],
        description="HTTP statuses that should trigger a retry.",
    )
    retry_on_timeout: bool = Field(
        True, description="Whether timeouts should be retried."
    )
    retry_on_connection_errors: bool = Field(
        True, description="Whether connection errors should be retried."
    )
    backoff: BackoffModel = Field(
        default_factory=BackoffModel,
        description="Backoff configuration applied between retries.",
    )


class RecordSelectorModel(BaseModel):
    """Record selector strategy for extracting arrays of records from responses."""

    field_path: List[str] = Field(
        default_factory=list,
        description="Airbyte-style JSON path used to locate the list of records in the payload.",
    )
    record_filter: Optional[str] = Field(
        default=None,
        description="Optional Jinja expression used to filter records client-side.",
    )
    cast_to_schema_types: bool = Field(
        False,
        description="Whether to cast values to the declared schema types during ingestion.",
    )


class PartitionModel(BaseModel):
    """Partition strategy configuration."""

    strategy: str = Field("none", description="Partitioning strategy to apply.")
    param: Optional[str] = Field(
        default=None,
        description="Query parameter used when partitioning by parameter range.",
    )
    values: Optional[Sequence[str]] = Field(
        default=None,
        description="Explicit values used for parameter range partitioning.",
    )
    range_start: Optional[Any] = Field(
        default=None,
        description="Inclusive start value for generated partition ranges.",
    )
    range_end: Optional[Any] = Field(
        default=None, description="Inclusive end value for generated partition ranges."
    )
    range_step: Optional[int] = Field(
        default=None, description="Step size used when generating partition ranges."
    )
    range_kind: Optional[str] = Field(
        default=None, description="Kind of range being generated (numeric or date)."
    )
    value_template: Optional[str] = Field(
        default=None,
        description="Template applied to each generated value before usage.",
    )
    extra_template: Optional[str] = Field(
        default=None,
        description="Template producing additional params for each generated partition value.",
    )
    endpoints: Optional[Sequence[str]] = Field(
        default=None,
        description="List of named endpoints used for endpoint partitioning.",
    )

    model_config = ConfigDict(populate_by_name=True)


class StreamModel(BaseModel):
    """Definition of the logical REST stream."""

    name: Optional[str] = Field(
        default=None,
        description="Optional stream name (defaults to path-derived name).",
    )
    path: str = Field(
        ..., description="Path requested for this stream; must start with '/'."
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Static query parameters sent on every request for this stream.",
    )
    headers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional headers sent on every request for this stream.",
    )
    pagination: PaginationModel = Field(
        default_factory=PaginationModel,
        description="Pagination configuration applied to this stream.",
    )
    incremental: IncrementalModel = Field(
        default_factory=IncrementalModel,
        description="Incremental cursor settings for this stream.",
    )
    infer_schema: Optional[bool] = Field(
        True,
        description="Whether to infer a schema for this stream when none is provided.",
    )
    schema_ddl: Optional[str] = Field(
        default=None,
        alias="schema",
        description="Optional Spark SQL DDL string describing the stream schema.",
    )
    record_selector: RecordSelectorModel = Field(
        default_factory=RecordSelectorModel,
        description="Record selector configuration for extracting arrays of records.",
    )
    error_handler: ErrorHandlerModel = Field(
        default_factory=ErrorHandlerModel,
        description="Error handling configuration specific to this stream.",
    )
    partition: Optional[PartitionModel] = Field(
        default=None,
        description="Partitioning strategy configuration for this stream (optional).",
    )

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    @property
    def schema(self) -> Optional[str]:
        return self.schema_ddl

    @schema.setter
    def schema(self, value: Optional[str]) -> None:
        self.schema_ddl = value


class SourceModel(BaseModel):
    """Source descriptor for the REST connector."""

    type: str = Field("rest", description="Source type (currently always 'rest').")
    base_url: str = Field(
        ..., description="Base URL for the API (without trailing slash)."
    )
    auth: Optional[AuthModel] = Field(
        default=None, description="Authentication configuration for this source."
    )


class PolymoConfig(BaseModel):
    """Pydantic model for building or loading Polymo configs."""

    version: str = Field(
        "0.1",
        description="Configuration format version. Currently only '0.1' is supported.",
    )
    base_url: str = Field(
        ..., description="Base URL for the REST API (without trailing slash)."
    )
    path: str = Field(
        ..., description="Path requested for the stream; must start with '/'."
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Static query parameters sent with every request.",
    )
    headers: Dict[str, Any] = Field(
        default_factory=dict,
        description="Optional HTTP headers included with every request.",
    )
    auth: Optional[AuthModel] = Field(
        default=None,
        description="Authentication block describing how to authorise requests.",
    )
    pagination: Optional[PaginationModel] = Field(
        default=None,
        description="Pagination strategy configuration. Defaults to type 'none' when omitted.",
    )
    incremental: Optional[IncrementalModel] = Field(
        default=None,
        description="Incremental cursor settings for change-data capture style loading.",
    )
    record_selector: Optional[RecordSelectorModel] = Field(
        default=None,
        description="Selector used to extract records from nested API payloads.",
    )
    error_handler: Optional[ErrorHandlerModel] = Field(
        default=None,
        description="Retry and backoff configuration applied to HTTP calls.",
    )
    partition: Optional[PartitionModel] = Field(
        default=None,
        description="Partitioning strategy for splitting work across multiple requests.",
    )
    infer_schema: Optional[bool] = Field(
        True,
        description="Whether Polymo should infer a schema when none is provided.",
    )
    schema_ddl: Optional[str] = Field(
        default=None,
        alias="schema",
        description="Optional Spark SQL DDL string describing the desired schema.",
    )

    model_config = ConfigDict(populate_by_name=True, protected_namespaces=())

    @classmethod
    def from_yaml(
        cls,
        yaml_text: str,
        *,
        token: Optional[str] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> "PolymoConfig":
        try:
            raw = yaml.safe_load(yaml_text) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Invalid YAML: {exc}") from exc

        return cls.from_dict(raw, token=token, options=options)

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
        *,
        token: Optional[str] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> "PolymoConfig":
        if not isinstance(data, Mapping):
            raise ConfigError("Configuration root must be a mapping")

        parsed = parse_config(dict(data), token=token, options=options)
        return cls.from_rest_config(parsed)

    @classmethod
    def from_rest_config(cls, config: RestSourceConfig) -> "PolymoConfig":
        payload = config_to_dict(config)
        source = payload.get("source", {})
        stream = payload.get("stream", {})

        return cls(
            version=payload.get("version", "0.1"),
            base_url=source.get("base_url", ""),
            path=stream.get("path", "/"),
            params=stream.get("params", {}) or {},
            headers=stream.get("headers", {}) or {},
            auth=AuthModel.model_validate(source.get("auth"))
            if source.get("auth")
            else None,
            pagination=PaginationModel.model_validate(stream.get("pagination"))
            if stream.get("pagination")
            else None,
            incremental=IncrementalModel.model_validate(stream.get("incremental"))
            if stream.get("incremental")
            else None,
            record_selector=RecordSelectorModel.model_validate(
                stream.get("record_selector")
            )
            if stream.get("record_selector")
            else None,
            error_handler=ErrorHandlerModel.model_validate(stream.get("error_handler"))
            if stream.get("error_handler")
            else None,
            partition=PartitionModel.model_validate(stream.get("partition"))
            if stream.get("partition")
            else None,
            infer_schema=stream.get("infer_schema"),
            schema_ddl=stream.get("schema"),
        )

    def _as_config_mapping(self) -> Dict[str, Any]:
        stream: Dict[str, Any] = {"path": self.path}
        if self.params:
            stream["params"] = dict(self.params)
        if self.headers:
            stream["headers"] = dict(self.headers)
        if self.infer_schema is not None:
            stream["infer_schema"] = self.infer_schema
        if self.schema_ddl is not None:
            stream["schema"] = self.schema_ddl
        if self.record_selector:
            stream["record_selector"] = self.record_selector.model_dump(
                exclude_none=True, by_alias=True
            )
        if self.error_handler:
            stream["error_handler"] = self.error_handler.model_dump(
                exclude_none=True, by_alias=True
            )
        if self.partition:
            stream["partition"] = self.partition.model_dump(
                exclude_none=True, by_alias=True
            )
        if self.incremental:
            stream["incremental"] = self.incremental.model_dump(
                exclude_none=True, by_alias=True
            )

        if self.pagination:
            pagination_payload = self.pagination.model_dump(
                exclude_none=True, by_alias=True
            )
        else:
            pagination_payload = {"type": "none"}
        if "type" not in pagination_payload:
            pagination_payload["type"] = "none"
        stream["pagination"] = pagination_payload

        config_payload: Dict[str, Any] = {
            "version": self.version,
            "source": {
                "type": "rest",
                "base_url": self.base_url,
            },
            "stream": stream,
        }

        if self.auth:
            config_payload["source"]["auth"] = self.auth.model_dump(
                exclude_none=True, by_alias=True
            )

        return config_payload

    @property
    def schema(self) -> Optional[str]:
        return self.schema_ddl

    @schema.setter
    def schema(self, value: Optional[str]) -> None:
        self.schema_ddl = value

    def to_rest_config(
        self,
        *,
        token: Optional[str] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> RestSourceConfig:
        payload = self._as_config_mapping()
        return parse_config(payload, token=token, options=options)

    def reader_config(
        self,
        *,
        token: Optional[str] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        return config_to_dict(self.to_rest_config(token=token, options=options))

    def dump_yaml(
        self,
        *,
        token: Optional[str] = None,
        options: Optional[Mapping[str, Any]] = None,
    ) -> str:
        return dump_config(self.to_rest_config(token=token, options=options))


__all__ = [
    "AuthModel",
    "PaginationModel",
    "IncrementalModel",
    "BackoffModel",
    "ErrorHandlerModel",
    "RecordSelectorModel",
    "PartitionModel",
    "StreamModel",
    "SourceModel",
    "PolymoConfig",
]
