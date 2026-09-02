from __future__ import annotations

import ast

from polymo.codegen import generate
from polymo.config import IncrementalConfig, PaginationConfig, PartitionConfig
from tests.codegen.helpers import assert_hygiene, make_config

# Batch @dp.table output must ingest through an inline PySpark custom Data
# Source (DataSource/DataSourceReader), the same way Lakeflow Declarative
# Pipelines requires and the streaming variant already does — never a
# driver-side spark.createDataFrame(list(fetch_records())).


def test_batch_with_schema_uses_explicit_schema_no_inference():
    config = make_config(base_url="https://x", schema="id BIGINT, name STRING")
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)
    assert "class RestSource(DataSource):" in script
    assert "class _Reader(DataSourceReader):" in script
    assert "def schema(self) -> str:" in script
    assert "return SCHEMA" in script
    assert "_infer_schema" not in script
    assert "spark.dataSource.register(RestSource)" in script
    assert 'spark.read.format("posts_source").load()' in script


def test_batch_without_schema_infers_schema_by_sampling():
    config = make_config(base_url="https://x")
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)
    assert "def _infer_schema() -> str:" in script
    assert "return _infer_schema()" in script
    # sampling, not the full stream — an explicit schema is recommended
    # precisely to avoid paying this cost / risk on every run
    assert "islice(fetch_records(), 50)" in script


def test_windowed_batch_partitions_over_windows():
    config = make_config(
        base_url="https://x",
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
    )
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)
    assert "from pyspark.sql.datasource import" in script
    assert "InputPartition" in script
    assert "def partitions(self) -> list[InputPartition]:" in script
    assert "InputPartition(index) for index in range(len(WINDOWS))" in script
    assert "fetch_records(**WINDOWS[partition.value])" in script


def test_non_windowed_batch_has_no_partitions_override():
    config = make_config(base_url="https://x")
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)
    assert "def partitions(self) -> list[InputPartition]:" not in script
    assert "InputPartition" not in script
    assert "def read(self, partition) -> Iterator[tuple]:" in script
    assert "fetch_records()" in script


def test_incremental_state_written_inside_read():
    config = make_config(
        base_url="https://x",
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
    )
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)

    reader_section = script.split("class _Reader(DataSourceReader):", 1)[1]
    read_body, _, rest = reader_section.partition("\n\ndef _cell(value: Any) -> Any:")
    assert "def read(self, partition) -> Iterator[tuple]:" in read_body
    assert "value = _cursor_of(record)" in read_body
    assert "if cursor is not None:\n            _write_state(cursor)" in read_body
    # the write must be inside read()/the class body, not left dangling in
    # module scope after it
    assert not rest.lstrip().startswith("_write_state")


def test_pagination_fanout_batch_partitions_over_pages():
    config = make_config(
        base_url="https://x",
        pagination=PaginationConfig(
            type="page", page_param="page", page_size=50, total_pages_header="X-Pages"
        ),
        partition=PartitionConfig(strategy="pagination"),
        schema="id BIGINT",
    )
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)
    assert "InputPartition" in script
    reader_section = script.split("class _Reader(DataSourceReader):", 1)[1]
    assert "def partitions(self) -> list[InputPartition]:" in reader_section
    assert "total = _probe_total_pages()" in reader_section
    assert "return [InputPartition(None)]" in reader_section
    assert "InputPartition(index) for index in range(total)" in reader_section
    assert "records = fetch_page(partition.value)" in reader_section
    assert "records = fetch_records()" in reader_section
    assert "WINDOWS" not in script


def test_incremental_windowed_state_written_inside_read():
    config = make_config(
        base_url="https://x",
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
        schema="id INT, updated STRING",
    )
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)

    reader_section = script.split("class _Reader(DataSourceReader):", 1)[1]
    assert "def partitions(self) -> list[InputPartition]:" in reader_section
    assert "def read(self, partition) -> Iterator[tuple]:" in reader_section
    assert "_write_state(cursor)" in reader_section


def test_batch_scripts_never_use_create_dataframe():
    configs = {
        "plain": make_config(base_url="https://x"),
        "schema": make_config(base_url="https://x", schema="id BIGINT"),
        "windowed": make_config(
            base_url="https://x",
            partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
        ),
        "incremental": make_config(
            base_url="https://x",
            incremental=IncrementalConfig(
                mode="cursor", cursor_param="since", cursor_field="updated"
            ),
        ),
        "windowed_incremental": make_config(
            base_url="https://x",
            partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
            incremental=IncrementalConfig(
                mode="cursor", cursor_param="since", cursor_field="updated"
            ),
            schema="id INT, updated STRING",
        ),
    }
    for name, config in configs.items():
        script = generate(config)
        assert "spark.createDataFrame" not in script, name
        assert "spark.read.format(" in script, name
