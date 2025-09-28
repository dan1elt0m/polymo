"""PySpark DataSource v2 implementation for REST-backed datasets."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterator, List, Mapping, Optional, Sequence

import pyarrow as pa
from pyspark.sql import SparkSession
from pyspark.sql.datasource import DataSource, DataSourceReader, InputPartition
from pyspark.sql.types import (
    BooleanType,
    DoubleType,
    LongType,
    StringType,
    StructField,
    StructType,
_parse_datatype_string
)

from .config import ConfigError, RestSourceConfig, load_config
from .rest_client import RestClient




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


class RestDataSourceReader(DataSourceReader):
    """Materialises REST API responses as Arrow record batches."""

    def __init__(self, config: RestSourceConfig, schema: StructType) -> None:
        self._config = config
        self._schema = schema

    def partitions(self) -> Sequence[InputPartition]:
        # Create one partition for the stream
        return [
            RestInputPartition(self._config)
        ]

    def read(self, partition: InputPartition) -> Iterator[pa.RecordBatch]:
        assert isinstance(partition, RestInputPartition)
        yield from _read_partition(partition.config, self._schema)


class RestInputPartition(InputPartition):
    def __init__(self, config: RestSourceConfig) -> None:
        super().__init__(value=None)
        self.config = config


def _load_source_config(options: Mapping[str, str]) -> RestSourceConfig:
    config_path = options.get("config_path")
    token = options.get("token")
    if not config_path:
        raise ConfigError("Option 'config_path' is required")

    return load_config(config_path, token)


def _infer_schema(config: RestSourceConfig) -> StructType:
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
        sample_value = next((row.get(key) for row in sample_records if row.get(key) is not None), None)
        dtype = _infer_type(sample_value)
        fields.append(StructField(key, dtype, nullable=True))
    return StructType(fields)


def _sample_stream(config: RestSourceConfig) -> List[Mapping[str, Any]]:
    with RestClient(base_url=config.base_url, auth=config.auth) as client:
        iterator = client.fetch_records(config.stream)
        first_page = next(iterator, [])
        if isinstance(first_page, list):
            return first_page[:50]
        return []


def _read_partition(config: RestSourceConfig, schema: StructType) -> Iterator[pa.RecordBatch]:
    """Read data from the stream."""
    with RestClient(base_url=config.base_url, auth=config.auth) as client:
        for page in client.fetch_records(config.stream):
            if not page:
                continue

            # Single stream format: use original record structure
            batch = _records_to_batch(page, schema)

            if batch.num_rows:
                yield batch


def _records_to_batch(records: List[Mapping[str, Any]], schema: StructType) -> pa.RecordBatch:
    arrays = []
    field_names = []

    for field in schema:
        column = [_coerce_value(record.get(field.name), field.dataType) for record in records]
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
    return pa.array([str(v) if v is not None else None for v in values], type=pa.string())
