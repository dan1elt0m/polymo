from __future__ import annotations

import pytest

from polymo.codegen import CodegenError, generate_core
from polymo.config import RecordSelectorConfig
from tests.codegen.helpers import make_config, run_generated


def test_field_path_with_wildcard(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        {"data": {"eu": [{"id": 1}], "us": [{"id": 2}]}},
        {},
    )
    config = make_config(
        base_url=http_server.url,
        record_selector=RecordSelectorConfig(field_path=["data", "*"]),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]


def test_record_filter_translated_to_python(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [{"id": 1, "ok": True}, {"id": 2, "ok": False}],
        {},
    )
    config = make_config(
        base_url=http_server.url,
        record_selector=RecordSelectorConfig(record_filter="{{ record['ok'] }}"),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1, "ok": True}]


def test_invalid_filter_raises_codegen_error():
    config = make_config(
        base_url="https://x",
        record_selector=RecordSelectorConfig(record_filter="{{ record[ }}"),
    )
    with pytest.raises(CodegenError):
        generate_core(config)
