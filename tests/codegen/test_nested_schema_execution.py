"""End-to-end roundtrip of nested-schema columns through a real Spark read.

Exercises the full generated script (unmodified — see the `spark_session`
fixture in conftest.py for how `pyspark.pipelines` is stubbed) against a
mock HTTP server returning nested dict/list records, via
`spark.read.format(...).load()`. This is the strongest evidence available
that:
  - the DDL validator's nested grammar (`_validate_type_expr` in config.py)
    is a subset of what Spark's own `StructType.fromDDL` accepts — SCHEMA
    is handed to Spark verbatim as a string, so if Spark rejected it, this
    read would raise before ever reaching the assertions below;
  - `_Reader.read()` passes nested dict/list values through as-is under an
    explicit schema (see dp.py.jinja's schema_ddl branch), landing them in
    real STRUCT/ARRAY/MAP columns instead of `_cell()`-stringifying them;
  - an *inferred* schema still stringifies nested values via `_cell()`
    (inference never produces a nested type, so a dict/list would
    otherwise crash the read).

Marked `@pytest.mark.spark`: each test spins up (or reuses, session-scoped)
a real local[1] SparkSession, so these are slower than the rest of the
suite.
"""

from __future__ import annotations

import json

import pytest

from polymo.codegen import generate
from tests.codegen.helpers import assert_hygiene, make_config


def _exec_and_register(script: str) -> None:
    """Exec a full generated script (core + dp wiring) so its DataSource
    self-registers with the active SparkSession, exactly like a user
    running the exported file would."""
    assert_hygiene(script)
    namespace: dict = {}
    exec(compile(script, "<generated>", "exec"), namespace)  # noqa: S102


@pytest.mark.spark
def test_explicit_nested_schema_roundtrips_struct_and_array(http_server, spark_session):
    record = {
        "id": 1,
        "address": {"street": "Main st", "zip": "1000"},
        "tags": ["a", "b"],
    }
    http_server.routes["/posts"] = lambda q, h, b: (200, [record], {})

    config = make_config(
        base_url=http_server.url,
        schema="id INT, address STRUCT<street: STRING, zip: STRING>, tags ARRAY<STRING>",
    )
    script = generate(config)
    _exec_and_register(script)

    df = spark_session.read.format("posts_source").load()
    rows = df.collect()

    assert len(rows) == 1
    row = rows[0]
    assert row.id == 1
    # A STRUCT/ARRAY column requires the actual structure, not a JSON
    # string — this is the behavior the nested-schema upgrade adds.
    assert row.address.street == "Main st"
    assert row.address.zip == "1000"
    assert row.tags == ["a", "b"]


@pytest.mark.spark
def test_inferred_schema_still_json_stringifies_nested_values(
    http_server, spark_session
):
    # Inference never produces a nested type, so a dict/list value must
    # still go through _cell()'s JSON-string fallback (pre-existing
    # behavior for the inferred path — must not regress).
    record = {"id": 2, "meta": {"street": "Elm st"}}
    http_server.routes["/posts"] = lambda q, h, b: (200, [record], {})

    config = make_config(base_url=http_server.url)  # infer_schema defaults True
    script = generate(config)
    assert "def _cell(value: Any) -> Any:" in script
    _exec_and_register(script)

    df = spark_session.read.format("posts_source").load()
    rows = df.collect()

    assert len(rows) == 1
    row = rows[0]
    assert row.id == 2
    # inferred as STRING; the dict landed as a JSON-encoded string, not a
    # struct
    assert isinstance(row.meta, str)
    assert json.loads(row.meta) == {"street": "Elm st"}


@pytest.mark.spark
def test_deeply_nested_schema_roundtrips(http_server, spark_session):
    record = {
        "id": 3,
        "profile": {
            "names": ["Ann", "Anne"],
            "score": {"value": 9, "grade": "A"},
        },
    }
    http_server.routes["/posts"] = lambda q, h, b: (200, [record], {})

    config = make_config(
        base_url=http_server.url,
        schema=(
            "id INT, profile STRUCT<names: ARRAY<STRING>,"
            " score: STRUCT<value: INT, grade: STRING>>"
        ),
    )
    script = generate(config)
    _exec_and_register(script)

    df = spark_session.read.format("posts_source").load()
    row = df.collect()[0]

    assert row.id == 3
    assert row.profile.names == ["Ann", "Anne"]
    assert row.profile.score.value == 9
    assert row.profile.score.grade == "A"
