from __future__ import annotations

import pytest

from polymo.config import PartitionConfig
from tests.codegen.helpers import make_config, run_generated

# _infer_schema() lives in core.py.jinja (itertools + fetch_records only, no
# pyspark) specifically so it can be exec-tested here via run_generated()
# against a real mock server, instead of only asserted on as a string in the
# generated source.


def test_windowed_inference_samples_every_window(http_server):
    # Regression: sampling only WINDOWS[0] silently dropped any column that
    # only shows up in a later window's records, forever (the dropped column
    # never appeared in the generated DDL at all).
    http_server.routes["/a"] = lambda q, h, b: (200, [{"a": 1}], {})
    http_server.routes["/b"] = lambda q, h, b: (200, [{"b": 2}], {})
    config = make_config(
        base_url=http_server.url,
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
    )
    module = run_generated(config)
    schema = module._infer_schema()
    assert "`a` BIGINT" in schema
    assert "`b` BIGINT" in schema


def test_int_then_float_widens_to_double(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"v": 5}, {"v": 5.5}], {})
    config = make_config(base_url=http_server.url)
    module = run_generated(config)
    assert module._infer_schema() == "`v` DOUBLE"


def test_bool_then_int_conflict_widens_to_string(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"v": True}, {"v": 1}], {})
    config = make_config(base_url=http_server.url)
    module = run_generated(config)
    assert module._infer_schema() == "`v` STRING"


def test_none_then_int_infers_bigint(http_server):
    # None contributes no vote; the field's type comes from the first
    # non-None value seen for it.
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"v": None}, {"v": 2}], {})
    config = make_config(base_url=http_server.url)
    module = run_generated(config)
    assert module._infer_schema() == "`v` BIGINT"


def test_empty_field_sample_raises_clear_error(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{}, {}], {})
    config = make_config(base_url=http_server.url)
    module = run_generated(config)
    with pytest.raises(RuntimeError, match="sampled records have no fields"):
        module._infer_schema()


def test_empty_response_raises_clear_error(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [], {})
    config = make_config(base_url=http_server.url)
    module = run_generated(config)
    with pytest.raises(RuntimeError, match="cannot infer a schema from an empty"):
        module._infer_schema()
