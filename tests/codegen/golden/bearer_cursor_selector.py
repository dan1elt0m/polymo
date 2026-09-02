"""Lakeflow Declarative Pipelines connector for posts."""

import time
from typing import Any, Iterator

import requests

BASE_URL: str = "https://api.example.com"
PATH: str = "/posts"
PARAMS: dict[str, Any] = {}
HEADERS: dict[str, str] = {}
TIMEOUT: float = 30.0

API_TOKEN: str = "REPLACE_ME"

MAX_RETRIES: int = 5


def _should_retry(status: int) -> bool:
    return 500 <= status <= 599 or status == 429


def _request(session: requests.Session, url: str, params: dict[str, Any] | None) -> requests.Response:
    delay = 1.0
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = session.get(url, params=params, timeout=TIMEOUT)
        except requests.exceptions.Timeout:
            if not True or attempt == MAX_RETRIES:
                raise
        except requests.exceptions.ConnectionError:
            if not True or attempt == MAX_RETRIES:
                raise
        else:
            if not _should_retry(response.status_code) or attempt == MAX_RETRIES:
                response.raise_for_status()
                return response
        time.sleep(delay)
        delay = min(delay * 2.0, 30.0) if 30.0 > 0 else delay * 2.0
    raise RuntimeError("unreachable")


def _dig(payload: Any, path: list[str]) -> Any:
    current = payload
    for key in path:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def _records(payload: Any) -> list[dict[str, Any]]:
    current = [payload]
    for segment in ['data']:
        next_level = []
        for item in current:
            if segment == "*":
                if isinstance(item, list):
                    next_level.extend(item)
                elif isinstance(item, dict):
                    next_level.extend(item.values())
            elif isinstance(item, dict) and segment in item:
                next_level.append(item[segment])
        current = next_level
    records = []
    for item in current:
        records.extend(item if isinstance(item, list) else [item])
    records = [r if isinstance(r, dict) else {"record": r} for r in records]
    return records


def fetch_records(extra_params: dict[str, Any] | None = None, path: str | None = None) -> Iterator[dict[str, Any]]:
    """Yield records, following the response cursor."""
    url_path = path or PATH
    session = requests.Session()
    session.headers.update(HEADERS)
    session.headers["Authorization"] = f"Bearer {API_TOKEN}"
    cursor = None
    while True:
        params = dict(PARAMS)
        if extra_params:
            params.update(extra_params)
        if cursor is not None:
            params["after"] = cursor
        response = _request(session, f"{BASE_URL}{url_path}", params)
        payload = response.json()
        records = _records(payload)
        if records:
            yield from records
        cursor = _dig(payload, ['meta', 'next'])
        if not cursor:
            return


def _infer_schema() -> str:
    from itertools import islice

    sample = list(islice(fetch_records(), 50))
    if not sample:
        raise RuntimeError(
            "cannot infer a schema from an empty response; set an explicit schema"
        )
    fields: dict[str, str] = {}
    for record in sample:
        for key, value in record.items():
            if value is None:
                continue
            if isinstance(value, bool):
                candidate = "BOOLEAN"
            elif isinstance(value, int):
                candidate = "BIGINT"
            elif isinstance(value, float):
                candidate = "DOUBLE"
            else:
                candidate = "STRING"
            current = fields.get(key)
            if current is None:
                fields[key] = candidate
            elif current == candidate:
                pass
            elif {current, candidate} == {"BIGINT", "DOUBLE"}:
                fields[key] = "DOUBLE"
            else:
                fields[key] = "STRING"
    if not fields:
        raise RuntimeError(
            "cannot infer a schema: sampled records have no fields; set an explicit"
            " schema"
        )
    return ", ".join(f"`{name}` {type_}" for name, type_ in fields.items())


from pyspark import pipelines as dp  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402

spark = SparkSession.getActiveSession()


from pyspark.sql.datasource import DataSource, DataSourceReader  # noqa: E402


class RestSource(DataSource):
    @classmethod
    def name(cls) -> str:
        return "posts_source"

    def schema(self) -> str:
        return _infer_schema()

    def reader(self, schema: Any) -> "_Reader":
        return _Reader(schema)


class _Reader(DataSourceReader):
    def __init__(self, schema: Any) -> None:
        self._columns: list[str] = [field.name for field in schema.fields]

    def read(self, partition) -> Iterator[tuple]:
        records = fetch_records()
        for record in records:
            yield tuple(_cell(record.get(column)) for column in self._columns)


def _cell(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value)
    return value


spark.dataSource.register(RestSource)


@dp.table(name="posts")
def posts():
    return spark.read.format("posts_source").load()
