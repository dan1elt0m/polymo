from __future__ import annotations

import ast

import pytest

from polymo.codegen import CodegenError, generate
from polymo.config import IncrementalConfig, PaginationConfig, PartitionConfig
from tests.codegen.helpers import assert_hygiene, make_config


def test_streaming_requires_schema_and_offset_or_page():
    config = make_config(base_url="https://x", streaming=True)
    with pytest.raises(CodegenError):
        generate(config)


def test_streaming_script_structure():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    script = generate(config)
    ast.parse(script)
    assert "class RestStreamSource" in script
    assert "SimpleDataSourceStreamReader" in script
    assert "spark.dataSource.register(RestStreamSource)" in script
    assert "spark.readStream" in script
    assert_hygiene(script)


def test_streaming_offset_pagination_requires_page_size():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="offset", offset_param="offset"),
    )
    with pytest.raises(CodegenError):
        generate(config)


def test_streaming_offset_pagination_with_page_size_script_structure():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(
            type="offset", offset_param="offset", page_size=100
        ),
    )
    script = generate(config)
    ast.parse(script)
    assert "class RestStreamSource" in script
    assert "page_index * 100" in script
    assert_hygiene(script)


def test_streaming_rejects_incremental_state():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
    )
    with pytest.raises(CodegenError):
        generate(config)


def test_streaming_rejects_partition_strategy():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
    )
    with pytest.raises(CodegenError):
        generate(config)


def test_streaming_reader_supports_checkpoint_recovery_replay():
    # pyspark's SimpleDataSourceStreamReader base implementation of
    # readBetweenOffsets raises PySparkNotImplementedError, which breaks
    # checkpoint-recovery replay unless the generated _Reader overrides it.
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    script = generate(config)
    ast.parse(script)
    assert (
        "def readBetweenOffsets(self, start: dict[str, Any], end: dict[str, Any]) -> Iterator[tuple]:"
        in script
    )
    assert_hygiene(script)


# Regression: `simpleStreamReader(self, schema)` is handed a real StructType
# by Spark (see pyspark.sql.datasource.DataSource.simpleStreamReader), the
# same way the batch DataSourceReader gets one — the generated streaming
# _Reader must derive its column names from `schema.fields`, not from a
# naive `SCHEMA.split(",")` (which corrupts on any comma inside a type:
# DECIMAL(p,s) and, now that nested DDL is accepted, STRUCT/ARRAY/MAP too).


def test_streaming_reader_derives_columns_from_schema_fields_no_naive_split():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT, name STRING",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)
    assert "COLUMNS" not in script
    assert "SCHEMA.split" not in script
    assert (
        "self._columns: list[str] = [field.name for field in schema.fields]" in script
    )
    assert "def __init__(self, schema: Any) -> None:" in script
    assert 'def simpleStreamReader(self, schema: Any) -> "_Reader":' in script
    assert "return _Reader(schema)" in script
    assert "for c in self._columns" in script


def test_streaming_nested_schema_generates_without_naive_column_split():
    # id INT, address STRUCT<street: STRING, zip: STRING> would have made
    # the old `f.split()[0] for f in SCHEMA.split(",")` derive
    # ['id', 'address', 'zip:'] — wrong on every count.
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id INT, address STRUCT<street: STRING, zip: STRING>",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)
    assert "COLUMNS" not in script
    assert "SCHEMA.split" not in script
    assert (
        "self._columns: list[str] = [field.name for field in schema.fields]" in script
    )


def test_streaming_decimal_schema_generates_without_naive_column_split():
    # decimal(10,2) has a comma inside the type, which is exactly what
    # broke the old naive split (the pre-existing backlog item this fix
    # resolves for free).
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id INT, price DECIMAL(10,2)",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)
    assert "COLUMNS" not in script
    assert "SCHEMA.split" not in script


@pytest.mark.spark
def test_streaming_reader_unit_derives_nested_columns_from_real_struct_type(
    spark_session,
):
    # Reader-unit-level verification (per the fix's own doc comment): build
    # a real StructType the way Spark would hand it to
    # simpleStreamReader(self, schema), and instantiate the generated
    # _Reader directly with it — no live streaming query needed for this,
    # just proof `self._columns` is derived correctly from schema.fields
    # for a nested/decimal DDL that would have corrupted the old naive
    # split. Full live streaming query execution remains untested (noted
    # in the report) — that would need an actual streaming source/sink and
    # checkpoint location, out of scope for a unit-level check.
    from pyspark.sql.types import StructType

    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id INT, price DECIMAL(10,2), address STRUCT<street: STRING, zip: STRING>",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    script = generate(config)
    assert_hygiene(script)

    namespace: dict = {}
    exec(compile(script, "<generated>", "exec"), namespace)  # noqa: S102

    schema = StructType.fromDDL(namespace["SCHEMA"])
    reader = namespace["_Reader"](schema)
    assert reader._columns == ["id", "price", "address"]
