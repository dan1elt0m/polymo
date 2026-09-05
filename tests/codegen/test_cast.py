"""`record_selector.cast_to_schema_types`: cast columns to the declared schema.

An XML API returns every value as text, and plenty of JSON APIs quote their
numbers; with an explicit typed schema Spark would reject those values on
ingest. With the option on, the generated `_records()` runs each top-level
scalar column through a per-type `_to_*` helper (only the helpers the
schema needs are emitted) before the reader, the streaming reader or the
builder preview ever see the record. Nested columns pass through untouched
and a value that can't be cast is left as-is, so Spark still reports it.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from polymo.codegen import generate, generate_bundle, generate_core
from polymo.config import RecordSelectorConfig
from tests.codegen.helpers import assert_hygiene, make_config, run_generated

CAST = RecordSelectorConfig(cast_to_schema_types=True)
SCHEMA = (
    "id INT, price DECIMAL(10,2), ok BOOLEAN, at TIMESTAMP, day DATE,"
    " note STRING, score DOUBLE, tags ARRAY<STRING>, meta STRUCT<a: STRING>"
)


def _config(http_server, schema: str = SCHEMA, **kwargs):
    return make_config(
        base_url=http_server.url, schema=schema, record_selector=CAST, **kwargs
    )


def test_cast_table_covers_only_top_level_scalar_columns():
    script = generate_core(
        make_config(base_url="https://x", schema=SCHEMA, record_selector=CAST)
    )
    assert_hygiene(script)
    assert "from typing import Any, Callable, Iterator" in script
    assert "from decimal import Decimal\n" in script
    assert "from datetime import datetime\n" in script
    assert "import json\n" in script
    assert (
        "CASTS: dict[str, Callable[[Any], Any]] = {\n"
        '    "id": _to_int,\n'
        '    "price": _to_decimal,\n'
        '    "ok": _to_bool,\n'
        '    "at": _to_timestamp,\n'
        '    "day": _to_date,\n'
        '    "note": _to_str,\n'
        '    "score": _to_float,\n'
        "}\n"
    ) in script
    assert "records = [_cast_record(record) for record in records]" in script


def test_only_the_helpers_the_schema_needs_are_emitted():
    script = generate_core(
        make_config(
            base_url="https://x", schema="id INT, name STRING", record_selector=CAST
        )
    )
    assert_hygiene(script)
    assert "def _to_int(value: Any) -> Any:" in script
    assert "def _to_str(value: Any) -> Any:" in script
    for absent in (
        "_to_float",
        "_to_bool",
        "_to_decimal",
        "_to_timestamp",
        "_to_date",
        "from decimal",
        "from datetime",
    ):
        assert absent not in script, absent


@pytest.mark.parametrize(
    "config",
    [
        make_config(base_url="https://x", schema="id INT"),
        make_config(base_url="https://x", record_selector=CAST),
    ],
    ids=["flag-off", "no-schema"],
)
def test_no_cast_code_without_the_flag_and_a_schema(config):
    script = generate(config)
    assert_hygiene(script)
    for needle in ("CASTS", "_cast_record", "_to_", "Callable", "Decimal"):
        assert needle not in script, needle


def test_values_are_cast_from_text(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [
            {
                "id": "7",
                "price": "10.90",
                "ok": "true",
                "at": "2024-05-13T15:30:42Z",
                "day": "2024-05-13",
                "note": {"k": 1},
                "score": "9.5",
                "tags": ["a"],
                "meta": {"a": "x"},
                "extra": "kept",
            }
        ],
        {},
    )
    [record] = list(run_generated(_config(http_server)).fetch_records())
    assert record == {
        "id": 7,
        "price": Decimal("10.90"),
        "ok": True,
        "at": datetime(2024, 5, 13, 15, 30, 42, tzinfo=timezone.utc),
        "day": date(2024, 5, 13),
        "note": '{"k": 1}',
        "score": 9.5,
        "tags": ["a"],
        "meta": {"a": "x"},
        "extra": "kept",
    }


def test_timestamp_offsets_and_native_types_are_preserved(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [
            {
                "id": 7,
                "price": 10.9,
                "ok": 1,
                "at": "2024-05-13T17:30:42+02:00",
                "day": "2024-05-13T17:30:42+02:00",
                "score": 9,
            }
        ],
        {},
    )
    [record] = list(run_generated(_config(http_server)).fetch_records())
    assert record["id"] == 7
    assert record["price"] == Decimal("10.9")
    assert record["ok"] is True
    assert record["at"].utcoffset().total_seconds() == 7200
    assert record["day"] == date(2024, 5, 13)
    assert record["score"] == 9.0 and isinstance(record["score"], float)


def test_null_and_uncastable_values_pass_through(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [
            {
                "id": "seven",
                "price": "n/a",
                "ok": "maybe",
                "at": 1715614242,
                "day": None,
                "note": None,
            }
        ],
        {},
    )
    [record] = list(run_generated(_config(http_server)).fetch_records())
    assert record == {
        "id": "seven",
        "price": "n/a",
        "ok": "maybe",
        "at": 1715614242,
        "day": None,
        "note": None,
    }


def test_record_filter_sees_raw_values_before_casting(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [{"id": "1", "ok": "true"}, {"id": "2", "ok": "false"}],
        {},
    )
    config = make_config(
        base_url=http_server.url,
        schema="id INT, ok BOOLEAN",
        record_selector=RecordSelectorConfig(
            record_filter="record['ok'] == 'true'", cast_to_schema_types=True
        ),
    )
    assert list(run_generated(config).fetch_records()) == [{"id": 1, "ok": True}]


def test_xml_text_and_attributes_are_cast(http_server):
    body = (
        '<items><item id="7" price="10.90"><year>1985</year><ok>yes</ok>'
        "<day>2024-05-13</day></item></items>"
    )
    http_server.routes["/items"] = lambda q, h, b: (200, body, {})
    config = make_config(
        base_url=http_server.url,
        name="items",
        path="/items",
        response_format="xml",
        xml_record_path=".//item",
        record_selector=CAST,
        schema="`@id` INT, `@price` DOUBLE, year INT, ok BOOLEAN, day DATE",
    )
    assert list(run_generated(config).fetch_records()) == [
        {"@id": 7, "@price": 10.9, "year": 1985, "ok": True, "day": date(2024, 5, 13)}
    ]


def test_bundle_client_carries_the_casts():
    files = generate_bundle(
        make_config(base_url="https://x", schema="id INT", record_selector=CAST),
        project_name="demo",
        catalog="main",
        schema="raw",
    )
    assert "CASTS" in files["src/demo/client.py"]
    assert "CASTS" not in files["src/demo/source.py"]


@pytest.mark.spark
def test_cast_values_land_in_typed_columns_through_spark(http_server, spark_session):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [
            {
                "id": "7",
                "price": "10.90",
                "ok": "true",
                "at": "2024-05-13T15:30:42Z",
                "day": "2024-05-13",
                "score": "9.5",
            }
        ],
        {},
    )
    config = make_config(
        base_url=http_server.url,
        schema="id INT, price DECIMAL(10,2), ok BOOLEAN, at TIMESTAMP, day DATE, score DOUBLE",
        record_selector=CAST,
    )
    script = generate(config)
    assert_hygiene(script)
    namespace: dict = {}
    exec(compile(script, "<generated>", "exec"), namespace)  # noqa: S102
    row = spark_session.read.format("posts_source").load().collect()[0]
    assert (row.id, row.price, row.ok, row.day, row.score) == (
        7,
        Decimal("10.90"),
        True,
        date(2024, 5, 13),
        9.5,
    )
    assert row.at.astimezone(timezone.utc) == datetime(
        2024, 5, 13, 15, 30, 42, tzinfo=timezone.utc
    )
