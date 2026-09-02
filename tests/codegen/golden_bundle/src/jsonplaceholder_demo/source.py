"""Spark DataSource for posts."""

from typing import Any, Iterator

from pyspark.sql.datasource import DataSource, DataSourceReader

from .client import fetch_records, _infer_schema

class JsonplaceholderDemoSource(DataSource):
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
