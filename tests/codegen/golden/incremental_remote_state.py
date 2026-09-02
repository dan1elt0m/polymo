"""Lakeflow Declarative Pipelines connector for issues."""

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Iterator

import requests

BASE_URL: str = "https://api.example.com"
PATH: str = "/issues"
PARAMS: dict[str, Any] = {}
HEADERS: dict[str, str] = {}
TIMEOUT: float = 30.0

STATE_PATH: str = "s3://team-bucket/state/issues.json"
STATE_KEY: str = "issues@https://api.example.com"
START_VALUE: str | None = "2024-01-01T00:00:00Z"
CURSOR_PARAM: str = "since"
CURSOR_FIELD: str = "updated_at"


def _state_fs() -> tuple[Any, str]:
    try:
        import fsspec  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "fsspec is required to use non-local incremental_state_path values"
        ) from exc
    return fsspec.core.url_to_fs(STATE_PATH)


def _load_state() -> dict[str, Any]:
    fs, path = _state_fs()
    if not fs.exists(path):
        return {}
    try:
        with fs.open(path, "r") as fh:
            payload = json.load(fh)
    except (OSError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _save_state(data: str) -> None:
    fs, path = _state_fs()
    directory = os.path.dirname(path)
    if directory and directory != "/":
        fs.makedirs(directory, exist_ok=True)
    with fs.open(path, "w") as fh:
        fh.write(data)


def _stored_cursor(payload: dict[str, Any]) -> str | None:
    streams = payload.get("streams")
    if isinstance(streams, dict):
        payload = streams
    entry = payload.get(STATE_KEY)
    if isinstance(entry, dict):
        entry = entry.get("cursor_value") or entry.get("value")
    return None if entry is None else str(entry)


def _read_state() -> str | None:
    """Return the stored cursor, falling back to START_VALUE."""
    return _stored_cursor(_load_state()) or START_VALUE


def _write_state(value: str) -> None:
    """Persist `value` unless the stored cursor is already at or past it."""
    payload = _load_state()
    stored = _stored_cursor(payload) or START_VALUE
    if stored is not None and value <= stored:
        return
    streams = payload.get("streams")
    if not isinstance(streams, dict):
        streams = {}
        payload["streams"] = streams
    streams[STATE_KEY] = {
        "cursor_param": CURSOR_PARAM,
        "cursor_field": CURSOR_FIELD,
        "cursor_value": value,
        "mode": "updated_at",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _save_state(json.dumps(payload, indent=2, sort_keys=True))


def _cursor_of(record: dict[str, Any]) -> str | None:
    value = record.get(CURSOR_FIELD)
    return None if value is None else str(value)


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
    """Yield records from the API (single page)."""
    url_path = path or PATH
    session = requests.Session()
    session.headers.update(HEADERS)
    params = dict(PARAMS)
    if extra_params:
        params.update(extra_params)
    state_cursor = _read_state()
    if state_cursor is not None:
        params.setdefault(CURSOR_PARAM, state_cursor)
    response = _request(session, f"{BASE_URL}{url_path}", params)
    records = _records(response.json())
    yield from records


from pyspark import pipelines as dp  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402

spark = SparkSession.getActiveSession()

SCHEMA: str = "id BIGINT, updated_at STRING"


from pyspark.sql.datasource import DataSource, DataSourceReader  # noqa: E402


class RestSource(DataSource):
    @classmethod
    def name(cls) -> str:
        return "issues_source"

    def schema(self) -> str:
        return SCHEMA

    def reader(self, schema: Any) -> "_Reader":
        return _Reader(schema)


class _Reader(DataSourceReader):
    def __init__(self, schema: Any) -> None:
        self._columns: list[str] = [field.name for field in schema.fields]

    def read(self, partition) -> Iterator[tuple]:
        records = fetch_records()
        cursor = None
        for record in records:
            value = _cursor_of(record)
            if value is not None and (cursor is None or value > cursor):
                cursor = value
            yield tuple(record.get(column) for column in self._columns)
        if cursor is not None:
            _write_state(cursor)


spark.dataSource.register(RestSource)


@dp.table(name="issues")
def issues():
    return spark.read.format("issues_source").load()
