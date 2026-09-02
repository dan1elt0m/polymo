"""Lakeflow Declarative Pipelines connector for posts."""

import time
from typing import Any, Iterator

import requests

BASE_URL: str = "https://api.example.com"
PATH: str = "/posts"
PARAMS: dict[str, Any] = {}
HEADERS: dict[str, str] = {}
TIMEOUT: float = 30.0

MAX_RETRIES: int = 5
INITIAL_DELAY: float = 1.0
MAX_DELAY: float = 30.0
BACKOFF: float = 2.0


def _should_retry(status: int) -> bool:
    return 500 <= status <= 599 or status == 429


def _request(session: requests.Session, url: str, params: dict[str, Any] | None) -> requests.Response:
    delay = INITIAL_DELAY
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = session.get(url, params=params, timeout=TIMEOUT)
        except requests.exceptions.Timeout:
            if attempt == MAX_RETRIES:
                raise
        except requests.exceptions.ConnectionError:
            if attempt == MAX_RETRIES:
                raise
        else:
            if not _should_retry(response.status_code) or attempt == MAX_RETRIES:
                response.raise_for_status()
                return response
        time.sleep(delay)
        delay = min(delay * BACKOFF, MAX_DELAY)
    raise RuntimeError("unreachable")


def _records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, dict):
        records = [payload]
        for key in ("data", "items", "results"):
            if key in payload and isinstance(payload[key], list):
                records = payload[key]
                break
    else:
        records = [payload]
    records = [r if isinstance(r, dict) else {"record": r} for r in records]
    return records


def fetch_records(extra_params: dict[str, Any] | None = None, path: str | None = None) -> Iterator[dict[str, Any]]:
    """Yield records, paginating with page."""
    url_path = path or PATH
    session = requests.Session()
    session.headers.update(HEADERS)
    page = 1
    while True:
        params = dict(PARAMS)
        if extra_params:
            params.update(extra_params)
        params["per_page"] = 100
        params["page"] = page
        response = _request(session, f"{BASE_URL}{url_path}", params)
        payload = response.json()
        records = _records(payload)
        if not records:
            return
        yield from records
        total = response.headers.get("X-Total-Pages")
        if total is not None and page >= int(total):
            return
        page += 1


def _page_response(page_index: int) -> requests.Response:
    session = requests.Session()
    session.headers.update(HEADERS)
    params = dict(PARAMS)
    params["per_page"] = 100
    params["page"] = page_index + 1
    return _request(session, f"{BASE_URL}{PATH}", params)


def fetch_page(page_index: int) -> list[dict[str, Any]]:
    """Fetch exactly one page of records."""
    response = _page_response(page_index)
    return _records(response.json())


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _probe_total_pages() -> int | None:
    """Fetch the first page and resolve the page count from the total hints."""
    response = _page_response(0)
    return _positive_int(response.headers.get("X-Total-Pages"))


from pyspark import pipelines as dp  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402

spark = SparkSession.getActiveSession()

SCHEMA: str = "id BIGINT"


from pyspark.sql.datasource import DataSource, DataSourceReader, InputPartition  # noqa: E402


class RestSource(DataSource):
    @classmethod
    def name(cls) -> str:
        return "posts_source"

    def schema(self) -> str:
        return SCHEMA

    def reader(self, schema: Any) -> "_Reader":
        return _Reader(schema)


class _Reader(DataSourceReader):
    def __init__(self, schema: Any) -> None:
        self._columns: list[str] = [field.name for field in schema.fields]

    def partitions(self) -> list[InputPartition]:
        total = _probe_total_pages()
        if total is None or total <= 1:
            return [InputPartition(None)]
        return [InputPartition(index) for index in range(total)]

    def read(self, partition) -> Iterator[tuple]:
        if partition.value is None:
            records = fetch_records()
        else:
            records = fetch_page(partition.value)
        for record in records:
            yield tuple(record.get(column) for column in self._columns)


spark.dataSource.register(RestSource)


@dp.table(name="posts")
def posts():
    return spark.read.format("posts_source").load()
