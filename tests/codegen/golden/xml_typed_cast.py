"""Lakeflow Declarative Pipelines connector for rates."""

import json
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Iterator

import requests
import xml.etree.ElementTree as ET

BASE_URL: str = "https://api.example.com"
PATH: str = "/rates.xml"
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


def _to_str(value: Any) -> Any:
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, (dict, list)):
        return json.dumps(value)
    return str(value)


def _to_bool(value: Any) -> Any:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "y", "on"):
            return True
        if lowered in ("false", "0", "no", "n", "off"):
            return False
        return value
    return value if value is None else bool(value)


def _to_int(value: Any) -> Any:
    try:
        return int(value)
    except (TypeError, ValueError):
        return value


def _to_float(value: Any) -> Any:
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


def _to_decimal(value: Any) -> Any:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except ArithmeticError:
        return value


def _to_timestamp(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value


def _to_date(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return value


CASTS: dict[str, Callable[[Any], Any]] = {
    "@currency": _to_str,
    "@rate": _to_float,
    "updated": _to_timestamp,
    "day": _to_date,
    "amount": _to_decimal,
    "active": _to_bool,
    "count": _to_int,
}


def _cast_record(record: dict[str, Any]) -> dict[str, Any]:
    for column, cast in CASTS.items():
        if column in record:
            record[column] = cast(record[column])
    return record


XML_RECORD_PATH: str = ".//rate"


def _local_name(tag: str) -> str:
    return tag.rpartition("}")[2]


def _records(root: ET.Element) -> list[dict[str, Any]]:
    records = []
    for element in root.findall(XML_RECORD_PATH):
        record: dict[str, Any] = {f"@{_local_name(key)}": value for key, value in element.attrib.items()}
        for child in element:
            record[_local_name(child.tag)] = child.text
        records.append(record)
    records = [_cast_record(record) for record in records]
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
    records = _records(ET.fromstring(response.content))
    yield from records


from pyspark import pipelines as dp  # noqa: E402
from pyspark.sql import SparkSession  # noqa: E402

spark = SparkSession.getActiveSession()

SCHEMA: str = "`@currency` STRING, `@rate` DOUBLE, updated TIMESTAMP, day DATE, amount DECIMAL(18,6), active BOOLEAN, count INT"


from pyspark.sql.datasource import DataSource, DataSourceReader  # noqa: E402


class RestSource(DataSource):
    @classmethod
    def name(cls) -> str:
        return "rates_source"

    def schema(self) -> str:
        return SCHEMA

    def reader(self, schema: Any) -> "_Reader":
        return _Reader(schema)


class _Reader(DataSourceReader):
    def __init__(self, schema: Any) -> None:
        self._columns: list[str] = [field.name for field in schema.fields]

    def read(self, partition) -> Iterator[tuple]:
        records = fetch_records()
        for record in records:
            yield tuple(record.get(column) for column in self._columns)


spark.dataSource.register(RestSource)


@dp.table(name="rates")
def rates():
    return spark.read.format("rates_source").load()
