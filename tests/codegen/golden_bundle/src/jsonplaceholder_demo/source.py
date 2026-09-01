"""posts — Spark DataSource (Databricks Asset Bundle).

Built on the fetch/schema helpers in `jsonplaceholder_demo.client`; edit this
file freely — it is not read by polymo again.
"""

from typing import Any, Iterator

from .client import fetch_records, _infer_schema

from pyspark.sql.datasource import DataSource, DataSourceReader  # noqa: E402


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
    """Nested structures become JSON strings; scalars pass through.

    Only used with an inferred schema — inference never produces a
    STRUCT/ARRAY/MAP column, so a dict/list value here would otherwise
    crash the read; JSON-encoding it into a STRING is the safe fallback.
    An explicit schema skips this: a STRUCT/ARRAY/MAP column needs the
    real structure, not a JSON string, so those values pass through as-is
    (see the schema-mode branch above).
    """
    if isinstance(value, (dict, list)):
        import json

        return json.dumps(value)
    return value
