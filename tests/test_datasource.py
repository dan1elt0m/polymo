from __future__ import annotations

import json
from typing import Dict, Iterable, List, Mapping, Optional

import pyarrow as pa
from pyspark.sql.types import LongType, StringType, StructField, StructType

import pytest

from polymo.config import (
    AuthConfig,
    ErrorHandlerConfig,
    IncrementalConfig,
    PaginationConfig,
    PartitionConfig,
    RecordSelectorConfig,
    RestSourceConfig,
    StreamConfig,
)
from polymo.datasource import RestDataSourceReader, RestDataSourceStreamReader
from polymo.rest_client import PaginationWindow, RestPage


class _FakeRestClient:
    def __init__(
        self,
        *_: object,
        pages_by_page: Optional[Dict[int, List[Mapping[str, int]]]] = None,
        pages_by_offset: Optional[Dict[int, List[Mapping[str, int]]]] = None,
        param_records: Optional[Dict[str, List[Mapping[str, int]]]] = None,
        endpoint_records: Optional[Dict[str, List[Mapping[str, int]]]] = None,
        total_pages: Optional[int] = None,
        total_records: Optional[int] = None,
        **__: object,
    ) -> None:
        self._pages_by_page = pages_by_page or {}
        self._pages_by_offset = pages_by_offset or {}
        self._param_records = param_records or {}
        self._endpoint_records = endpoint_records or {}
        self._total_pages = total_pages
        self._total_records = total_records

    def __enter__(self) -> "_FakeRestClient":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def peek_page(self, stream: StreamConfig) -> Optional[RestPage]:
        payload: Dict[str, object] = {}
        if self._total_pages is not None:
            payload.setdefault("meta", {})  # type: ignore[assignment]
            payload["meta"]["total_pages"] = self._total_pages  # type: ignore[index]
        if self._total_records is not None:
            payload.setdefault("meta", {})  # type: ignore[assignment]
            payload["meta"]["total_records"] = self._total_records  # type: ignore[index]

        if self._pages_by_page:
            records = self._pages_by_page.get(stream.pagination.start_page or 1, [])
        else:
            records = self._pages_by_offset.get(stream.pagination.start_offset or 0, [])

        return RestPage(
            records=records,
            payload=payload,
            url="https://example.com/peek",
            status_code=200,
            headers={},
        )

    def fetch_records(
        self,
        stream: StreamConfig,
        *,
        window: Optional[PaginationWindow] = None,
    ) -> Iterable[List[Mapping[str, int]]]:
        def _iterator() -> Iterable[List[Mapping[str, int]]]:
            if window is not None and window.endpoint_name and self._endpoint_records:
                yield self._endpoint_records.get(window.endpoint_name, [])
                return

            if window is not None and window.extra_params and self._param_records:
                param_name, value = next(iter(window.extra_params.items()))
                key = str(value)
                yield self._param_records.get(key, [])
                return

            if window is not None and window.page is not None and self._pages_by_page:
                yield self._pages_by_page.get(int(window.page), [])
                return

            if (
                window is not None
                and window.offset is not None
                and self._pages_by_offset
            ):
                yield self._pages_by_offset.get(int(window.offset), [])
                return

            if self._pages_by_page:
                for key in sorted(self._pages_by_page):
                    yield self._pages_by_page[key]
                return

            if self._pages_by_offset:
                for key in sorted(self._pages_by_offset):
                    yield self._pages_by_offset[key]
                return

            if self._param_records:
                for key in sorted(self._param_records):
                    yield self._param_records[key]
                return

            if self._endpoint_records:
                for key in sorted(self._endpoint_records):
                    yield self._endpoint_records[key]
                return

            yield []

        return _iterator()


def _build_config(
    pagination: PaginationConfig,
    *,
    options: Optional[Dict[str, str]] = None,
    partition: Optional[PartitionConfig] = None,
) -> RestSourceConfig:
    stream = StreamConfig(
        name="sample",
        path="/items",
        params={},
        headers={},
        pagination=pagination,
        incremental=IncrementalConfig(),
        infer_schema=True,
        schema=None,
        record_selector=RecordSelectorConfig(),
        error_handler=ErrorHandlerConfig(),
        partition=partition or PartitionConfig(),
    )

    return RestSourceConfig(
        version="0.1",
        base_url="https://example.com",
        auth=AuthConfig(),
        stream=stream,
        options=dict(options or {}),
    )


def _build_id_schema() -> StructType:
    return StructType([StructField("id", LongType(), True)])


def _build_endpoint_schema() -> StructType:
    return StructType(
        [
            StructField("endpoint_name", StringType(), False),
            StructField("data", StringType(), True),
        ]
    )


def _extract_ids(batches: Iterable[pa.RecordBatch]) -> List[int]:
    ids: List[int] = []
    for batch in batches:
        ids.extend(batch.column(0).to_pylist())
    return ids


def test_partitions_page_pagination(monkeypatch) -> None:
    pagination = PaginationConfig(
        type="page",
        page_size=1,
        limit_param="per_page",
        page_param="page",
        start_page=1,
        total_pages_path=("meta", "total_pages"),
    )
    config = _build_config(pagination, options={"partition_strategy": "pagination"})

    pages = {
        1: [{"id": 1}],
        2: [{"id": 2}],
        3: [{"id": 3}],
    }

    def factory(*args: object, **kwargs: object) -> _FakeRestClient:
        return _FakeRestClient(*args, pages_by_page=pages, total_pages=3, **kwargs)

    monkeypatch.setattr("polymo.datasource.RestClient", factory)

    reader = RestDataSourceReader(config, _build_id_schema())
    partitions = reader.partitions()

    assert len(partitions) == 3

    observed = []
    for partition in partitions:
        observed.extend(_extract_ids(reader.read(partition)))

    assert observed == [1, 2, 3]


def test_partitions_offset_pagination(monkeypatch) -> None:
    pagination = PaginationConfig(
        type="offset",
        page_size=2,
        limit_param="limit",
        offset_param="offset",
        start_offset=0,
        total_records_path=("meta", "total_records"),
    )
    config = _build_config(pagination, options={"partition_strategy": "pagination"})

    pages = {
        0: [{"id": 1}, {"id": 2}],
        2: [{"id": 3}, {"id": 4}],
        4: [{"id": 5}],
    }

    def factory(*args: object, **kwargs: object) -> _FakeRestClient:
        return _FakeRestClient(*args, pages_by_offset=pages, total_records=5, **kwargs)

    monkeypatch.setattr("polymo.datasource.RestClient", factory)

    reader = RestDataSourceReader(config, _build_id_schema())
    partitions = reader.partitions()

    assert len(partitions) == 3

    observed = []
    for partition in partitions:
        observed.extend(_extract_ids(reader.read(partition)))

    assert observed == [1, 2, 3, 4, 5]


def test_partitions_param_range(monkeypatch) -> None:
    pagination = PaginationConfig(type="none")
    config = _build_config(
        pagination,
        options={
            "partition_strategy": "param_range",
            "partition_param": "page",
            "partition_values": "1,2,3",
        },
    )

    records = {
        "1": [{"id": 10}],
        "2": [{"id": 20}],
        "3": [{"id": 30}],
    }

    def factory(*args: object, **kwargs: object) -> _FakeRestClient:
        return _FakeRestClient(*args, param_records=records, **kwargs)

    monkeypatch.setattr("polymo.datasource.RestClient", factory)

    reader = RestDataSourceReader(config, _build_id_schema())
    partitions = reader.partitions()

    assert len(partitions) == 3

    observed = []
    for partition in partitions:
        observed.extend(_extract_ids(reader.read(partition)))

    assert observed == [10, 20, 30]


def test_partitions_param_range_from_yaml(monkeypatch) -> None:
    pagination = PaginationConfig(type="none")
    partition = PartitionConfig(
        strategy="param_range",
        param="page",
        range_start=1,
        range_end=3,
        range_step=1,
        range_kind="numeric",
    )
    config = _build_config(pagination, partition=partition)

    records = {
        "1": [{"id": 10}],
        "2": [{"id": 20}],
        "3": [{"id": 30}],
    }

    def factory(*args: object, **kwargs: object) -> _FakeRestClient:
        return _FakeRestClient(*args, param_records=records, **kwargs)

    monkeypatch.setattr("polymo.datasource.RestClient", factory)

    reader = RestDataSourceReader(config, _build_id_schema())
    partitions = reader.partitions()

    assert len(partitions) == 3

    observed = []
    for partition in partitions:
        observed.extend(_extract_ids(reader.read(partition)))

    assert observed == [10, 20, 30]


def test_partitions_endpoint_strategy(monkeypatch) -> None:
    pagination = PaginationConfig(type="none")
    config = _build_config(
        pagination,
        options={
            "partition_strategy": "endpoints",
            "partition_endpoints": "users:/users,repos:/repos",
        },
    )

    endpoint_records = {
        "repos": [{"id": 2}],
        "users": [{"id": 1}],
    }

    def factory(*args: object, **kwargs: object) -> _FakeRestClient:
        return _FakeRestClient(*args, endpoint_records=endpoint_records, **kwargs)

    monkeypatch.setattr("polymo.datasource.RestClient", factory)

    reader = RestDataSourceReader(config, _build_endpoint_schema())
    partitions = reader.partitions()

    assert len(partitions) == 2

    rows = []
    for partition in partitions:
        for batch in reader.read(partition):
            endpoint_names = batch.column(0).to_pylist()
            payloads = batch.column(1).to_pylist()
            rows.extend(zip(endpoint_names, payloads))

    expected = {
        ("users", json.dumps({"id": 1}, separators=(",", ":"), sort_keys=True)),
        ("repos", json.dumps({"id": 2}, separators=(",", ":"), sort_keys=True)),
    }
    assert set(rows) == expected


@pytest.mark.smoke
def test_stream_reader_batches(monkeypatch, tmp_path) -> None:
    pagination = PaginationConfig(type="none")
    progress_path = tmp_path / "stream-progress.json"
    config = _build_config(
        pagination,
        options={
            "stream_batch_size": "2",
            "stream_progress_path": str(progress_path),
        },
    )

    batches = [[{"id": 1}, {"id": 2}], [{"id": 3}]]

    def fake_fetch(self: RestDataSourceStreamReader) -> List[Mapping[str, int]]:
        if batches:
            return batches.pop(0)
        return []

    monkeypatch.setattr(
        "polymo.datasource.RestDataSourceStreamReader._fetch_batch", fake_fetch
    )

    reader = RestDataSourceStreamReader(config, _build_id_schema())

    start_offset = reader.initialOffset()
    end_offset = reader.latestOffset()
    partitions = reader.partitions(start_offset, end_offset)
    rows = list(reader.read(partitions[0]))
    assert rows == [(1,), (2,)]
    reader.commit(end_offset)

    if progress_path.exists():
        payload = json.loads(progress_path.read_text())
        assert payload["offset"] == end_offset["offset"]

    next_end = reader.latestOffset()
    next_rows = list(reader.read(reader.partitions(end_offset, next_end)[0]))
    assert next_rows == [(3,)]
    reader.commit(next_end)
