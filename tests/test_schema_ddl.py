"""Unit tests for the pyspark-free nested-DDL validator (`_validate_ddl_syntax`).

Covers the grammar `_validate_ddl_syntax`/`_validate_type_expr` accept:
scalars, DECIMAL(p,s), ARRAY<T>, MAP<K,V>, STRUCT<name[:] T, ...>, and
backtick-quoted field names (outer and inner) — plus the garbage that must
still be rejected with a clear message. Exercised both through the private
validator directly (for precise error-shape checks) and through the public
`parse_config` entrypoint (for the end-to-end `ConfigError` wrapping).
"""

from __future__ import annotations

import pytest

from polymo.config import ConfigError, parse_config
from polymo.config import _validate_ddl_syntax as validate_ddl


def _config(schema: str) -> dict:
    return {
        "version": 0.1,
        "source": {"type": "rest", "base_url": "https://api.test"},
        "stream": {"name": "sample", "path": "/objects", "schema": schema},
    }


# --- accepted: flat (pre-existing behavior must not regress) ---------------


@pytest.mark.parametrize(
    "schema",
    [
        "id INT, name STRING",
        "id INT, price DECIMAL(10,2)",
        "id INT, price DECIMAL",
        "id BIGINT, ok BOOLEAN, ts TIMESTAMP, d DATE, v VARIANT",
    ],
)
def test_flat_schema_still_accepted(schema: str) -> None:
    validate_ddl(schema)
    parse_config(_config(schema))


# --- accepted: nested types --------------------------------------------------


@pytest.mark.parametrize(
    "schema",
    [
        "id INT, address STRUCT<street: STRING, zip: STRING>",
        "id INT, address STRUCT<street STRING, zip STRING>",  # no-colon inner syntax
        "id INT, tags ARRAY<STRING>",
        "id INT, matrix ARRAY<ARRAY<INT>>",
        "id INT, meta MAP<STRING, STRING>",
        "id INT, meta MAP<STRING, STRUCT<a: INT, b: STRING>>",
        "id INT, s STRUCT<a: ARRAY<STRUCT<x: INT, y: DECIMAL(5,2)>>>",
        "id INT, s STRUCT<a: INT, b: STRUCT<c: STRING>>",  # nested struct in struct
    ],
)
def test_nested_schema_accepted(schema: str) -> None:
    validate_ddl(schema)
    parse_config(_config(schema))


# --- accepted: backtick-quoted names ----------------------------------------


@pytest.mark.parametrize(
    "schema",
    [
        "`first name` STRING, id INT",
        "id INT, address STRUCT<`first name`: STRING>",
        "id INT, address STRUCT<`first name` STRING>",
        "`weird,name` INT, id STRING",  # comma inside backticks must not split fields
        "`with<bracket` INT",  # bracket char inside backticks must not affect depth
    ],
)
def test_backtick_quoted_names_accepted(schema: str) -> None:
    validate_ddl(schema)
    parse_config(_config(schema))


# --- rejected: garbage -------------------------------------------------------


@pytest.mark.parametrize(
    "schema",
    [
        "id INT, s STRUCT<a: INT",  # unbalanced '<'
        "id INT, s STRUCT<>",  # empty struct
        "id INT, s STRUCT<a: FOOBAR>",  # unknown scalar inside struct
        "id INT, a ARRAY<>",  # empty array element type
        "id INT, a ARRAY<FOOBAR>",  # unknown scalar inside array
        "id INT, m MAP<STRING>",  # map needs exactly key,value
        "id INT, m MAP<STRING, STRING, STRING>",  # too many map type args
        "id FOOBAR",  # unknown top-level scalar
        "",  # empty schema
        "id INT, `unterminated STRING",  # unterminated backtick
        "id INT, s STRUCT<a: INT>extra>",  # trailing garbage after struct close
        "id",  # missing type
    ],
)
def test_garbage_rejected(schema: str) -> None:
    with pytest.raises(ValueError):
        validate_ddl(schema)


def test_garbage_wrapped_in_config_error() -> None:
    with pytest.raises(ConfigError, match="Invalid schema DDL"):
        parse_config(_config("id INT, s STRUCT<a: FOOBAR>"))
