"""Lakeflow Declarative Pipelines connector for gekentekende_voertuigen."""

import time
from typing import Any, Iterator

import requests

BASE_URL: str = "https://opendata.rdw.nl"
PATH: str = "/resource/m9d7-ebf2.json"
PARAMS: dict[str, Any] = {"$order": "kenteken"}
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
    """Yield records, paginating with $offset/$limit."""
    url_path = path or PATH
    session = requests.Session()
    session.headers.update(HEADERS)
    offset = 0
    while True:
        params = dict(PARAMS)
        if extra_params:
            params.update(extra_params)
        params["$limit"] = 1000
        params["$offset"] = offset
        response = _request(session, f"{BASE_URL}{url_path}", params)
        records = _records(response.json())
        if not records:
            return
        yield from records
        offset += 1000


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
        return "gekentekende_voertuigen_source"

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


@dp.table(name="gekentekende_voertuigen")
def gekentekende_voertuigen():
    return spark.read.format("gekentekende_voertuigen_source").load()
