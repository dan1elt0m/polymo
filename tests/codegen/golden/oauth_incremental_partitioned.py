"""Lakeflow Declarative Pipelines connector for posts."""

import time
from typing import Any, Iterator

import requests
import json
import os

BASE_URL: str = "https://api.example.com"
PATH: str = "/posts"
PARAMS: dict[str, Any] = {}
HEADERS: dict[str, str] = {}
TIMEOUT: float = 30.0

WINDOWS: list[dict[str, Any]] = [{"path": "/a"}, {"path": "/b"}]

STATE_PATH: str = "posts_state.json"


def _read_state() -> dict[str, Any]:
    if not os.path.exists(STATE_PATH):
        return {}
    with open(STATE_PATH) as fh:
        return json.load(fh)


def _write_state(cursor: Any) -> None:
    if cursor is None:
        return
    with open(STATE_PATH, "w") as fh:
        json.dump({"cursor": cursor}, fh)

CLIENT_SECRET: str = "REPLACE_ME"
TOKEN_URL: str = "https://api.example.com/token"


def get_token() -> str:
    """Fetch an OAuth2 access token (client credentials grant)."""
    payload = {
        "grant_type": "client_credentials",
        "client_id": "cid",
        "client_secret": CLIENT_SECRET,
    }
    response = requests.post(TOKEN_URL, data=payload, timeout=TIMEOUT)
    response.raise_for_status()
    return response.json()["access_token"]

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
    """Yield records from the API (single page)."""
    url_path = path or PATH
    session = requests.Session()
    session.headers.update(HEADERS)
    session.headers["Authorization"] = f"Bearer {get_token()}"
    params = dict(PARAMS)
    if extra_params:
        params.update(extra_params)
    state_cursor = _read_state().get("cursor")
    if state_cursor is not None:
        params["since"] = state_cursor
    response = _request(session, f"{BASE_URL}{url_path}", params)
    records = _records(response.json())
    yield from records


from pyspark import pipelines as dp  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402

spark = SparkSession.getActiveSession()

SCHEMA: str = "id BIGINT, updated STRING"


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
        return [InputPartition(index) for index in range(len(WINDOWS))]

    def read(self, partition) -> Iterator[tuple]:
        records = fetch_records(**WINDOWS[partition.value])
        cursor = None
        for record in records:
            value = record.get("updated")
            if value is not None and (cursor is None or value > cursor):
                cursor = value
            yield tuple(record.get(column) for column in self._columns)
        _write_state(cursor)


spark.dataSource.register(RestSource)


@dp.table(name="posts")
def posts():
    return spark.read.format("posts_source").load()
