"""PySpark DataSource v2 implementation for REST-backed datasets."""

from __future__ import annotations

import base64
import json
import math
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence, Tuple

import pyarrow as pa
from pyspark.sql import SparkSession
from pyspark.sql.datasource import (
    DataSource,
    DataSourceReader,
    DataSourceStreamReader,
    InputPartition,
)
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
    _parse_datatype_string,
)

from .config import (
    ConfigError,
    PaginationConfig,
    PartitionConfig,
    RestSourceConfig,
    load_config,
    parse_config,
)
from .rest_client import PaginationWindow, RestClient, RestPage


class ApiReader(DataSource):
    """Expose `spark.read.format("polymo")` over YAML-defined REST streams."""

    def __init__(self, options: Dict[str, str]) -> None:
        super().__init__(options)
        self._config = _load_source_config(self.options)
        self._schema: Optional[StructType] = None

    @classmethod
    def name(cls) -> str:
        return "polymo"

    def schema(self) -> StructType:
        if self._config.stream.schema:
            # Use user-provided schema if available
            SparkSession.builder.getOrCreate()
            self._schema = _parse_datatype_string(self._config.stream.schema)
        if self._schema is None:
            # Always infer schema when no explicit schema is provided
            self._schema = _infer_schema(self._config)

        return self._schema

    def reader(self, schema: StructType) -> DataSourceReader:
        return RestDataSourceReader(self._config, self.schema())

    def streamReader(self, schema: StructType) -> DataSourceStreamReader:
        return RestDataSourceStreamReader(self._config, self.schema())


class RestInputPartition(InputPartition):
    def __init__(
        self, config: RestSourceConfig, window: Optional[PaginationWindow] = None
    ) -> None:
        super().__init__(value=None)
        self.config = config
        self.window = window


class RestStreamInputPartition(InputPartition):
    def __init__(self, start: int, end: int) -> None:
        super().__init__(value=None)
        self.start = start
        self.end = end


class RestDataSourceReader(DataSourceReader):
    """Materialises REST API responses as Arrow record batches."""

    def __init__(self, config: RestSourceConfig, schema: StructType) -> None:
        self._config = config
        self._schema = schema

    def partitions(self) -> Sequence[InputPartition]:
        windows = _plan_partitions(self._config)
        if windows:
            return [RestInputPartition(self._config, window=w) for w in windows]
        return [RestInputPartition(self._config)]

    def read(self, partition: InputPartition) -> Iterator[pa.RecordBatch]:
        assert isinstance(partition, RestInputPartition)
        yield from _read_partition(partition.config, self._schema, partition.window)


class RestDataSourceStreamReader(DataSourceStreamReader):
    """Structured Streaming reader for REST-backed datasets."""

    def __init__(self, config: RestSourceConfig, schema: StructType) -> None:
        self._config = config
        self._schema = schema

        options = dict(config.options or {})
        raw_batch_size = options.get("stream_batch_size", 100)
        try:
            self._batch_size = int(raw_batch_size)
        except (TypeError, ValueError):
            self._batch_size = 100
        if self._batch_size <= 0:
            self._batch_size = 100

        progress_path = options.get("stream_progress_path")
        if isinstance(progress_path, str) and progress_path.strip():
            self._progress_path = Path(progress_path).expanduser()
        else:
            self._progress_path = None

        self._current_offset = self._load_progress()

    def initialOffset(self) -> Dict[str, int]:
        return {"offset": self._current_offset}

    def latestOffset(self) -> Dict[str, int]:
        self._current_offset += 1
        return {"offset": self._current_offset}

    def partitions(
        self, start: Dict[str, int], end: Dict[str, int]
    ) -> Sequence[InputPartition]:
        start_offset = int(start.get("offset", 0))
        end_offset = int(end.get("offset", 0))
        return [RestStreamInputPartition(start_offset, end_offset)]

    def commit(self, end: Dict[str, int]) -> None:
        offset = int(end.get("offset", self._current_offset))
        self._current_offset = offset
        self._save_progress(offset)

    def read(self, partition: RestStreamInputPartition) -> Iterator[Tuple[Any, ...]]:
        records = self._fetch_batch()
        rows: List[Tuple[Any, ...]] = []
        for record in records:
            if not isinstance(record, Mapping):
                continue
            row = tuple(
                _coerce_value(record.get(field.name), field.dataType)
                for field in self._schema
            )
            rows.append(row)
        return iter(rows)

    def _fetch_batch(self) -> List[Mapping[str, Any]]:
        results: List[Mapping[str, Any]] = []
        if self._batch_size <= 0:
            return results

        with RestClient(
            base_url=self._config.base_url,
            auth=self._config.auth,
            options=self._config.options,
        ) as client:
            iterator = client.fetch_records(self._config.stream)
            for page in iterator:
                if not isinstance(page, list):
                    continue
                for record in page:
                    if not isinstance(record, Mapping):
                        continue
                    results.append(record)
                    if len(results) >= self._batch_size:
                        break
                if len(results) >= self._batch_size:
                    break
        return results

    def _load_progress(self) -> int:
        if self._progress_path is None:
            return 0
        try:
            if not self._progress_path.exists():
                return 0
            payload = json.loads(self._progress_path.read_text())
            value = payload.get("offset")
            if isinstance(value, int):
                return value
            if isinstance(value, str) and value.isdigit():
                return int(value)
        except Exception:
            return 0
        return 0

    def _save_progress(self, offset: int) -> None:
        if self._progress_path is None:
            return
        try:
            self._progress_path.parent.mkdir(parents=True, exist_ok=True)
            self._progress_path.write_text(json.dumps({"offset": offset}))
        except Exception:
            pass


def _get_databricks_secret(scope: str, key: str) -> str:
    """Gets a secret from the Databricks secret scope."""
    from databricks.sdk import WorkspaceClient
    w = WorkspaceClient()
    secret_response = w.secrets.get_secret(scope=scope, key=key)
    decoded_secret = base64.b64decode(secret_response.value).decode("utf-8")
    return decoded_secret

def _load_databricks_oauth_credentials(options: Mapping[str, str]) -> Optional[Tuple[str, str]]:
    oauth_client_id_scope = options.get("oauth_client_id_scope")
    oauth_client_id_key = options.get("oauth_client_id_key")
    oauth_client_secret_scope = options.get("oauth_client_secret_scope")
    oauth_client_secret_key = options.get("oauth_client_secret_key")
    if oauth_client_id_scope and oauth_client_id_key and oauth_client_secret_scope and oauth_client_secret_key:
        try:
            client_id = _get_databricks_secret(oauth_client_id_scope, oauth_client_id_key)
            client_secret = _get_databricks_secret(oauth_client_secret_scope, oauth_client_secret_key)
            return client_id, client_secret
        except Exception:
            raise ConfigError(
                f"Failed to access Databricks secrets for OAuth client credentials: "
                f"client_id scope='{oauth_client_id_scope}' key='{oauth_client_id_key}'; "
                f"client_secret scope='{oauth_client_secret_scope}' key='{oauth_client_secret_key}'"
            )
    return None

def _load_databricks_token(options: Mapping[str, str]) -> Optional[str]:
    token_scope = options.get("token_scope")
    token_key = options.get("token_key")
    if token_scope and token_key:
        try:
            return dbutils.secrets.get(scope=token_scope, key=token_key)
        except Exception:
            raise ConfigError(
                f"Failed to access Databricks secret for token: scope='{token_scope}' key='{token_key}'"
            )
    return None

def _load_source_config(options: Mapping[str, str]) -> RestSourceConfig:
    config_path = options.get("config_path")
    config_json = options.get("config_json")
    token = options.get("token")

    specified = [bool(config_path), bool(config_json)]
    if sum(specified) > 1:
        raise ConfigError(
            "Specify only one of 'config_path' or 'config_json' for the Polymo data source",
        )

    runtime_options = {
        key: value
        for key, value in options.items()
        if key not in {"config_path", "config_json", "token"}
    }

    databricks_token = _load_databricks_token(options)
    databricks_oauth_credentials = _load_databricks_oauth_credentials(options)
    if databricks_token:
        token = databricks_token
    if databricks_oauth_credentials:
        runtime_options["oauth_client_id"], runtime_options["oauth_client_secret"] = databricks_oauth_credentials

    if config_json:
        try:
            raw_config = json.loads(config_json)
        except json.JSONDecodeError as exc:
            raise ConfigError(f"Invalid JSON supplied via 'config_json': {exc}") from exc
        return parse_config(raw_config, token=token, options=runtime_options)

    if config_path:
        return load_config(config_path, token, runtime_options)

    raise ConfigError("One of 'config_path' or 'config_json' must be provided")


def _infer_schema(config: RestSourceConfig) -> StructType:
    if config.stream.partition and config.stream.partition.strategy == "endpoints":
        return StructType(
            [
                StructField("endpoint_name", StringType(), True),
                StructField("data", StringType(), True),
            ]
        )

    sample_records = _sample_stream(config)
    if not sample_records:
        return StructType([])

    seen: Dict[str, None] = {}
    ordered_keys: List[str] = []
    for record in sample_records:
        for key in record.keys():
            if key not in seen:
                seen[key] = None
                ordered_keys.append(key)

    fields = []
    for key in ordered_keys:
        sample_value = next(
            (row.get(key) for row in sample_records if row.get(key) is not None), None
        )
        dtype = _infer_type(sample_value)
        fields.append(StructField(key, dtype, nullable=True))
    return StructType(fields)


def _sample_stream(config: RestSourceConfig) -> List[Mapping[str, Any]]:
    windows = _plan_partitions(config)
    first_window = windows[0] if windows else None

    with RestClient(
        base_url=config.base_url, auth=config.auth, options=config.options
    ) as client:
        iterator = client.fetch_records(config.stream, window=first_window)
        first_page = next(iterator, [])
        if isinstance(first_page, list):
            return first_page[:50]
        return []


def _plan_partitions(config: RestSourceConfig) -> List[PaginationWindow]:
    partition = config.stream.partition
    strategy = partition.strategy if partition else "none"

    if strategy == "none":
        partition = _partition_from_options(config.options, partition)
        strategy = partition.strategy
        if strategy == "none":
            return []
        config = replace(config, stream=replace(config.stream, partition=partition))

    if strategy == "pagination":
        return _plan_pagination_partitions(config)
    if strategy == "param_range":
        return _plan_param_range_partitions(config)
    if strategy == "endpoints":
        return _plan_endpoint_partitions(config)
    return []


def _partition_from_options(
    options: Mapping[str, Any],
    fallback: Optional[PartitionConfig] = None,
) -> PartitionConfig:
    strategy_raw = str(options.get("partition_strategy", "")).strip()
    if not strategy_raw:
        return fallback or PartitionConfig()

    strategy = strategy_raw

    if strategy == "pagination":
        return PartitionConfig(strategy="pagination")

    if strategy == "param_range":
        param_raw = options.get("partition_param")
        values_raw = options.get("partition_values")
        range_start_raw = options.get("partition_range_start")
        range_end_raw = options.get("partition_range_end")
        range_step_raw = options.get("partition_range_step")
        range_kind_raw = options.get("partition_range_kind")
        value_template_raw = options.get("partition_value_template")
        extra_template_raw = options.get("partition_extra_template")

        def _clean_str(value: Any) -> Optional[str]:
            if value is None:
                return None
            text = str(value).strip()
            return text or None

        range_step = None
        if range_step_raw is not None and str(range_step_raw).strip():
            try:
                range_step = int(str(range_step_raw).strip())
            except ValueError as exc:  # pragma: no cover - defensive casting
                raise ConfigError("partition_range_step must be an integer") from exc

        cleaned_kind = _clean_str(range_kind_raw)
        if cleaned_kind and cleaned_kind not in {"numeric", "date"}:
            raise ConfigError("partition_range_kind must be 'numeric' or 'date'")

        return PartitionConfig(
            strategy="param_range",
            param=_clean_str(param_raw),
            values=_clean_str(values_raw),
            range_start=_clean_str(range_start_raw),
            range_end=_clean_str(range_end_raw),
            range_step=range_step,
            range_kind=cleaned_kind or None,
            value_template=_clean_str(value_template_raw),
            extra_template=_clean_str(extra_template_raw),
        )

    if strategy == "endpoints":
        endpoints_raw = options.get("partition_endpoints")
        if endpoints_raw is None:
            raise ConfigError("partition_endpoints is required for endpoints strategy")

        entries = _parse_endpoint_entries(endpoints_raw)
        endpoints: List[str] = []
        for entry in entries:
            name = str(entry.get("name") or "").strip()
            path = str(entry.get("path") or "").strip()
            if not path:
                raise ConfigError(
                    "Each endpoint must include a path when using endpoints strategy"
                )
            endpoints.append(f"{name}:{path}" if name else path)

        return PartitionConfig(strategy="endpoints", endpoints=tuple(endpoints))

    raise ConfigError(f"Unsupported partition strategy: {strategy}")


def _plan_pagination_partitions(config: RestSourceConfig) -> List[PaginationWindow]:
    pagination = config.stream.pagination
    if pagination.type not in {"page", "offset"}:
        return []

    page_size = pagination.page_size
    if page_size is None or page_size <= 0:
        return []

    has_total_hint = any(
        (
            pagination.total_pages_path,
            pagination.total_pages_header,
            pagination.total_records_path,
            pagination.total_records_header,
        )
    )
    if not has_total_hint:
        return []

    with RestClient(
        base_url=config.base_url, auth=config.auth, options=config.options
    ) as client:
        first_page = client.peek_page(config.stream)

    if first_page is None:
        return []

    total_pages = _resolve_total_pages(first_page, config.stream.pagination, page_size)
    if total_pages is None or total_pages <= 1:
        return []

    windows: List[PaginationWindow] = []
    if pagination.type == "page":
        start_page = pagination.start_page or 1
        for index in range(total_pages):
            windows.append(PaginationWindow(page=start_page + index, max_pages=1))
    else:  # offset pagination
        start_offset = pagination.start_offset or 0
        for index in range(total_pages):
            offset = start_offset + index * page_size
            windows.append(PaginationWindow(offset=offset, max_pages=1))

    return windows


def _plan_param_range_partitions(config: RestSourceConfig) -> List[PaginationWindow]:
    partition = config.stream.partition

    if not partition.param:
        raise ConfigError("partition_strategy='param_range' requires 'param' to be set")

    param = partition.param

    values = _parse_partition_values(partition.values)
    if not values:
        # Generate values from range configuration if explicit values not provided
        values = _generate_range_values_from_config(partition)

    if not values:
        raise ConfigError(
            "partition_strategy='param_range' requires either 'values' or range configuration"
        )

    template_str = partition.value_template
    extra_template_str = partition.extra_template

    windows: List[PaginationWindow] = []
    for value in values:
        formatted = _apply_value_template(value, template_str)
        extra_params: Dict[str, Any] = {param: formatted}
        if extra_template_str:
            extra_params.update(_render_extra_params(extra_template_str, formatted))
        windows.append(PaginationWindow(extra_params=extra_params))

    return windows


def _plan_endpoint_partitions(config: RestSourceConfig) -> List[PaginationWindow]:
    partition = config.stream.partition

    if not partition.endpoints:
        raise ConfigError(
            "partition_strategy='endpoints' requires 'endpoints' to be defined"
        )

    windows: List[PaginationWindow] = []

    # Handle the case where endpoints is a tuple of strings
    for endpoint in partition.endpoints:
        # Simple format - just path
        if ":" in endpoint:
            # Format: "name:/path"
            parts = endpoint.split(":", 1)
            name = parts[0].strip()
            path = parts[1].strip()
            windows.append(
                PaginationWindow(
                    path_override=path,
                    endpoint_name=name,
                )
            )
        else:
            # Just use the endpoint as both name and path
            windows.append(
                PaginationWindow(
                    path_override=endpoint,
                    endpoint_name=endpoint,
                )
            )

    return windows


def _resolve_total_pages(
    page: RestPage,
    pagination: PaginationConfig,
    page_size: int,
) -> Optional[int]:
    payload = page.payload
    headers = page.headers

    total_pages_candidate = _coerce_positive_int(
        _extract_value_from_path(payload, pagination.total_pages_path)
        if pagination.total_pages_path
        else None
    )
    if total_pages_candidate is None and pagination.total_pages_header:
        total_pages_candidate = _coerce_positive_int(
            headers.get(pagination.total_pages_header)
        )

    if total_pages_candidate is not None and total_pages_candidate > 0:
        return total_pages_candidate

    total_records_candidate = _coerce_positive_int(
        _extract_value_from_path(payload, pagination.total_records_path)
        if pagination.total_records_path
        else None
    )
    if total_records_candidate is None and pagination.total_records_header:
        total_records_candidate = _coerce_positive_int(
            headers.get(pagination.total_records_header)
        )

    if total_records_candidate is None or total_records_candidate <= 0:
        return None

    return max(1, math.ceil(total_records_candidate / page_size))


def _extract_value_from_path(payload: Any, path: Sequence[str]) -> Any:
    if not path:
        return None
    try:
        from polymo.rest_client import _first_value_from_path

        return _first_value_from_path(payload, path)
    except Exception:
        return None


def _coerce_positive_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        converted = int(str(value).strip())
    except (TypeError, ValueError):
        return None
    return converted if converted >= 0 else None


def _parse_partition_values(raw: Any) -> List[str]:
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


def _generate_range_values(options: Mapping[str, Any]) -> List[str]:
    start_raw = options.get("partition_range_start")
    end_raw = options.get("partition_range_end")
    if start_raw is None or end_raw is None:
        return []

    kind = str(options.get("partition_range_kind", "numeric")).strip().lower()
    step_raw = options.get("partition_range_step")

    if kind in {"numeric", "number", "int", "integer"}:
        start = int(str(start_raw))
        end = int(str(end_raw))
        step = int(str(step_raw)) if step_raw is not None else 1
        if step <= 0:
            raise ConfigError(
                "partition_range_step must be greater than 0 for numeric ranges"
            )

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

    if kind in {"date", "day", "daily"}:
        start_date = datetime.fromisoformat(str(start_raw)).date()
        end_date = datetime.fromisoformat(str(end_raw)).date()
        step_days = int(str(step_raw)) if step_raw is not None else 1
        if step_days <= 0:
            raise ConfigError(
                "partition_range_step must be greater than 0 for date ranges"
            )

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

    raise ConfigError(
        "partition_range_kind must be 'numeric' or 'date' when using partition_strategy='param_range'"
    )


def _generate_range_values_from_config(partition) -> List[str]:
    """Generate range values from the partition configuration."""
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
        except (ValueError, TypeError):
            raise ConfigError("Range values must be valid integers for numeric ranges")

        if step <= 0:
            raise ConfigError("range_step must be greater than 0 for numeric ranges")

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
        except (ValueError, TypeError):
            raise ConfigError("Range values must be valid ISO dates for date ranges")

        if step_days <= 0:
            raise ConfigError("range_step must be greater than 0 for date ranges")

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

    raise ConfigError(
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
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive
        raise ConfigError("partition_extra_template must be valid JSON") from exc
    if not isinstance(payload, Mapping):
        raise ConfigError("partition_extra_template must resolve to a JSON object")
    return {str(key): str(payload[key]) for key in payload}


def _parse_endpoint_entries(raw: Any) -> List[Dict[str, Any]]:
    if isinstance(raw, (list, tuple)):
        entries = [entry for entry in raw if isinstance(entry, Mapping)]
        return [dict(entry) for entry in entries]

    text = str(raw).strip()
    if not text:
        return []

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        entries: List[Dict[str, Any]] = []
        for chunk in text.split(","):
            if not chunk.strip():
                continue
            if ":" not in chunk:
                raise ConfigError(
                    "partition_endpoints string format must be 'name:/path,name:/other'"
                )
            name, path = chunk.split(":", 1)
            entries.append({"name": name.strip(), "path": path.strip()})
        return entries

    if isinstance(parsed, Mapping):
        return [dict(parsed)]
    if isinstance(parsed, list):
        results: List[Dict[str, Any]] = []
        for item in parsed:
            if not isinstance(item, Mapping):
                raise ConfigError(
                    "partition_endpoints entries must be objects with name/path"
                )
            entry = dict(item)
            params = entry.get("params")
            if isinstance(params, str):
                params = json.loads(params)
                entry["params"] = params
            results.append(entry)
        return results

    raise ConfigError(
        "partition_endpoints must be a JSON array or comma-separated name:path list"
    )


def _read_partition(
    config: RestSourceConfig,
    schema: StructType,
    window: Optional[PaginationWindow] = None,
) -> Iterator[pa.RecordBatch]:
    """Read data from the stream."""
    with RestClient(
        base_url=config.base_url, auth=config.auth, options=config.options
    ) as client:
        endpoint_name = window.endpoint_name if window else None

        for page in client.fetch_records(config.stream, window=window):
            if not page:
                continue

            if endpoint_name is not None:
                records: List[Mapping[str, Any]] = [
                    {"endpoint_name": endpoint_name, "data": record} for record in page
                ]
            else:
                records = page

            batch = _records_to_batch(records, schema)

            if batch.num_rows:
                yield batch


def _records_to_batch(
    records: List[Mapping[str, Any]], schema: StructType
) -> pa.RecordBatch:
    arrays = []
    field_names = []

    for field in schema:
        column = [
            _coerce_value(record.get(field.name), field.dataType) for record in records
        ]
        arrays.append(_to_arrow_array(column, field.dataType))
        field_names.append(field.name)

    return pa.record_batch(arrays, names=field_names)


def _infer_type(value: Any) -> StringType | LongType | DoubleType | BooleanType:
    if isinstance(value, bool):
        return BooleanType()
    if isinstance(value, int):
        return LongType()
    if isinstance(value, float):
        return DoubleType()
    # For nested structures default to string JSON payloads.
    return StringType()


def _coerce_value(value: Any, data_type: Any) -> Any:
    if value is None:
        return None
    if isinstance(data_type, StringType):
        if isinstance(value, (dict, list)):
            return json.dumps(value, separators=(",", ":"), sort_keys=True)
        return str(value)
    if isinstance(data_type, LongType):
        return int(value)
    if isinstance(data_type, DoubleType):
        return float(value)
    if isinstance(data_type, BooleanType):
        return bool(value)
    return str(value)


def _to_arrow_array(values: List[Any], data_type: Any) -> pa.Array:
    if isinstance(data_type, StringType):
        return pa.array(values, type=pa.string())
    if isinstance(data_type, LongType):
        return pa.array(values, type=pa.int64())
    if isinstance(data_type, DoubleType):
        return pa.array(values, type=pa.float64())
    if isinstance(data_type, BooleanType):
        return pa.array(values, type=pa.bool_())
    return pa.array(
        [str(v) if v is not None else None for v in values], type=pa.string()
    )
