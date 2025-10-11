# Polymo Configuration Reference

> This document is generated automatically from the Pydantic models in `polymo.pydantic_config`.


## PolymoConfig

Pydantic model for building or loading Polymo configs.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `version` | `str` | `0.1` | Configuration format version. Currently only '0.1' is supported. |
| `base_url` | `str` | — | Base URL for the REST API (without trailing slash). |
| `path` | `str` | — | Path requested for the stream; must start with '/'. |
| `params` | `Dict[str, Any]` | `<factory>` | Static query parameters sent with every request. |
| `headers` | `Dict[str, Any]` | `<factory>` | Optional HTTP headers included with every request. |
| `auth` | `Optional[AuthModel]` | `None` | Authentication block describing how to authorise requests. See [AuthModel](#authmodel). |
| `pagination` | `Optional[PaginationModel]` | `None` | Pagination strategy configuration. Defaults to type 'none' when omitted. See [PaginationModel](#paginationmodel). |
| `incremental` | `Optional[IncrementalModel]` | `None` | Incremental cursor settings for change-data capture style loading. See [IncrementalModel](#incrementalmodel). |
| `record_selector` | `Optional[RecordSelectorModel]` | `None` | Selector used to extract records from nested API payloads. See [RecordSelectorModel](#recordselectormodel). |
| `error_handler` | `Optional[ErrorHandlerModel]` | `None` | Retry and backoff configuration applied to HTTP calls. See [ErrorHandlerModel](#errorhandlermodel). |
| `partition` | `Optional[PartitionModel]` | `None` | Partitioning strategy for splitting work across multiple requests. See [PartitionModel](#partitionmodel). |
| `infer_schema` | `Optional[bool]` | `True` | Whether Polymo should infer a schema when none is provided. |
| `schema_ddl` | `Optional[str]` | `None` | Optional Spark SQL DDL string describing the desired schema. |

## AuthModel

Authentication settings for the REST source.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | `str` | `none` | Authentication strategy ('none', 'bearer', or 'oauth2'). |
| `token` | `Optional[str]` | `None` | Static bearer token supplied directly in the config (rare, use runtime tokens instead). |
| `token_url` | `Optional[str]` | `None` | OAuth2 token endpoint used for client-credentials flows (required for oauth2). |
| `client_id` | `Optional[str]` | `None` | OAuth2 client identifier (required for oauth2). |
| `client_secret` | `Optional[str]` | `None` | Optional OAuth2 client secret embedded in the config (use runtime secrets when possible). |
| `scope` | `Optional[List[str]]` | `None` | Scopes requested during OAuth2 token exchange (list of strings). |
| `audience` | `Optional[str]` | `None` | Optional OAuth2 audience parameter. |
| `extra_params` | `Optional[Dict[str, Any]]` | `None` | Additional key/value pairs merged into the OAuth2 token request payload. |

## PaginationModel

Pagination configuration mirroring the YAML contract.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `type` | `str` | `none` | Pagination strategy type. |
| `page_size` | `Optional[int]` | `None` | Number of records requested per page. |
| `limit_param` | `Optional[str]` | `None` | Query parameter controlling page size. |
| `offset_param` | `Optional[str]` | `None` | Query parameter incremented for offset pagination. |
| `start_offset` | `Optional[int]` | `None` | Initial offset value for offset pagination. |
| `page_param` | `Optional[str]` | `None` | Query parameter incremented for page pagination. |
| `start_page` | `Optional[int]` | `None` | Initial page number for page pagination. |
| `cursor_param` | `Optional[str]` | `None` | Query parameter used to send the cursor value. |
| `cursor_path` | `Optional[List[str]]` | `None` | JSON path extracting the next cursor from a payload. |
| `next_url_path` | `Optional[List[str]]` | `None` | JSON path pointing to the next page URL in the payload. |
| `cursor_header` | `Optional[str]` | `None` | HTTP response header containing the next cursor. |
| `initial_cursor` | `Optional[str]` | `None` | Cursor value supplied for the very first request. |
| `stop_on_empty_response` | `Optional[bool]` | `None` | Stop pagination when the API returns an empty page. |
| `total_pages_path` | `Optional[List[str]]` | `None` | JSON path pointing to the total number of pages. |
| `total_pages_header` | `Optional[str]` | `None` | HTTP header containing the total number of pages. |
| `total_records_path` | `Optional[List[str]]` | `None` | JSON path pointing to the total number of records. |
| `total_records_header` | `Optional[str]` | `None` | HTTP header containing the total number of records. |

## IncrementalModel

Incremental cursor settings.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `mode` | `Optional[str]` | `None` | Incremental sync mode (reserved for future use). |
| `cursor_param` | `Optional[str]` | `None` | Request parameter used to send the cursor value. |
| `cursor_field` | `Optional[str]` | `None` | Field inside each record holding the cursor value. |

## RecordSelectorModel

Record selector strategy for extracting arrays of records from responses.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `field_path` | `List[str]` | `<factory>` | Airbyte-style JSON path used to locate the list of records in the payload. |
| `record_filter` | `Optional[str]` | `None` | Optional Jinja expression used to filter records client-side. |
| `cast_to_schema_types` | `bool` | `False` | Whether to cast values to the declared schema types during ingestion. |

## PartitionModel

Partition strategy configuration.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `strategy` | `str` | `none` | Partitioning strategy to apply. |
| `param` | `Optional[str]` | `None` | Query parameter used when partitioning by parameter range. |
| `values` | `Optional[Sequence[UnionType[str, int]]]` | `None` | Explicit values used for parameter range partitioning. |
| `range_start` | `Optional[Any]` | `None` | Inclusive start value for generated partition ranges. |
| `range_end` | `Optional[Any]` | `None` | Inclusive end value for generated partition ranges. |
| `range_step` | `Optional[int]` | `None` | Step size used when generating partition ranges. |
| `range_kind` | `Optional[str]` | `None` | Kind of range being generated (numeric or date). |
| `value_template` | `Optional[str]` | `None` | Template applied to each generated value before usage. |
| `extra_template` | `Optional[str]` | `None` | Template producing additional params for each generated partition value. |
| `endpoints` | `Optional[Sequence[str]]` | `None` | List of named endpoints used for endpoint partitioning. |

## BackoffModel

Retry backoff strategy.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `initial_delay_seconds` | `float` | `1.0` | Initial delay in seconds before performing the first retry. |
| `max_delay_seconds` | `float` | `30.0` | Maximum delay in seconds between retries. |
| `multiplier` | `float` | `2.0` | Exponential multiplier applied to the delay after each retry. |

## ErrorHandlerModel

Error handling configuration.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `max_retries` | `int` | `5` | Maximum number of retries before failing. |
| `retry_statuses` | `List[str]` | `<factory>` | HTTP statuses that should trigger a retry. |
| `retry_on_timeout` | `bool` | `True` | Whether timeouts should be retried. |
| `retry_on_connection_errors` | `bool` | `True` | Whether connection errors should be retried. |
| `backoff` | `BackoffModel` | `<factory>` | Backoff configuration applied between retries. See [BackoffModel](#backoffmodel). |

## StreamModel

Definition of the logical REST stream.

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | `Optional[str]` | `None` | Optional stream name (defaults to path-derived name). |
| `path` | `str` | — | Path requested for this stream; must start with '/'. |
| `params` | `Dict[str, Any]` | `<factory>` | Static query parameters sent on every request for this stream. |
| `headers` | `Dict[str, Any]` | `<factory>` | Optional headers sent on every request for this stream. |
| `pagination` | `PaginationModel` | `<factory>` | Pagination configuration applied to this stream. See [PaginationModel](#paginationmodel). |
| `incremental` | `IncrementalModel` | `<factory>` | Incremental cursor settings for this stream. See [IncrementalModel](#incrementalmodel). |
| `infer_schema` | `Optional[bool]` | `True` | Whether to infer a schema for this stream when none is provided. |
| `schema_ddl` | `Optional[str]` | `None` | Optional Spark SQL DDL string describing the stream schema. |
| `record_selector` | `RecordSelectorModel` | `<factory>` | Record selector configuration for extracting arrays of records. See [RecordSelectorModel](#recordselectormodel). |
| `error_handler` | `ErrorHandlerModel` | `<factory>` | Error handling configuration specific to this stream. See [ErrorHandlerModel](#errorhandlermodel). |
| `partition` | `Optional[PartitionModel]` | `None` | Partitioning strategy configuration for this stream (optional). See [PartitionModel](#partitionmodel). |
