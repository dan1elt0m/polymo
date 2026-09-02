"""Lakeflow Declarative Pipelines connector for posts."""

import time
from typing import Any, Iterator

import requests

BASE_URL: str = "https://jsonplaceholder.typicode.com"
PATH: str = "/posts"
PARAMS: dict[str, Any] = {"_limit": 20}
HEADERS: dict[str, str] = {}
TIMEOUT: float = 30.0

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
    params = dict(PARAMS)
    if extra_params:
        params.update(extra_params)
    response = _request(session, f"{BASE_URL}{url_path}", params)
    records = _records(response.json())
    yield from records


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
