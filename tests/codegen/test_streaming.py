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
