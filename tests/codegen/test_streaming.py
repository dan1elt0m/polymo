from __future__ import annotations

import ast

import pytest

from polymo.codegen import CodegenError, generate
from polymo.config import PaginationConfig
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
