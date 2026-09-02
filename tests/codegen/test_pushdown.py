"""Filter pushdown in the generated batch reader.

`stream.pushdown_params` maps DataFrame columns to API query parameters; the
generated `_Reader.pushFilters()` keeps an `EqualTo` on a mapped top-level
column (sent as that query parameter on every request the read makes) and
hands every other filter back to Spark.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from pyspark.sql.datasource import EqualTo, GreaterThan, In, IsNull, Not

from polymo.codegen import CodegenError, generate
from polymo.config import IncrementalConfig, PaginationConfig, PartitionConfig
from tests.codegen.helpers import (
    assert_hygiene,
    fake_schema,
    make_config,
    run_generated_script,
)

PUSHDOWN = {"status": "status", "owner_id": "owner"}


def _queries(http_server) -> list[dict[str, str]]:
    result = []
    for _method, path, _headers in http_server.log:
        query = parse_qs(urlparse(path).query)
        result.append({key: values[0] for key, values in query.items()})
    return result


def _reader(config):
    module = run_generated_script(config)
    return module, module._Reader(fake_schema("id"))


def _echo(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}], {})


def test_mapped_equal_to_is_pushed_and_sent_as_query_param(http_server):
    _echo(http_server)
    config = make_config(
        base_url=http_server.url, pushdown_params=PUSHDOWN, schema="id BIGINT"
    )
    module, reader = _reader(config)
    assert module.PUSHDOWN_PARAMS == PUSHDOWN

    unsupported = list(
        reader.pushFilters([EqualTo(("status",), "active"), EqualTo(("owner_id",), 42)])
    )
    assert unsupported == []
    assert reader._pushed == {"status": "active", "owner": "42"}

    assert list(reader.read(None)) == [(1,)]
    assert _queries(http_server) == [{"status": "active", "owner": "42"}]


@pytest.mark.parametrize(
    "filter_",
    [
        EqualTo(("title",), "x"),
        EqualTo(("status",), None),
        EqualTo(("meta", "status"), "active"),
        In(("status",), ["a", "b"]),
        GreaterThan(("owner_id",), 1),
        IsNull(("status",)),
        Not(EqualTo(("status",), "active")),
    ],
    ids=["unmapped", "null-value", "nested", "in", "gt", "isnull", "not"],
)
def test_unsupported_filters_are_returned_unchanged_and_not_sent(http_server, filter_):
    _echo(http_server)
    config = make_config(
        base_url=http_server.url, pushdown_params=PUSHDOWN, schema="id BIGINT"
    )
    _module, reader = _reader(config)
    assert list(reader.pushFilters([filter_])) == [filter_]
    assert reader._pushed == {}
    list(reader.read(None))
    assert _queries(http_server) == [{}]


def test_mixed_filters_keep_only_the_pushable_ones(http_server):
    _echo(http_server)
    config = make_config(
        base_url=http_server.url, pushdown_params=PUSHDOWN, schema="id BIGINT"
    )
    _module, reader = _reader(config)
    rest = In(("status",), ["a"])
    unsupported = list(
        reader.pushFilters(
            [EqualTo(("status",), "active"), rest, GreaterThan(("id",), 3)]
        )
    )
    assert unsupported == [rest, GreaterThan(("id",), 3)]
    assert reader._pushed == {"status": "active"}


def test_push_filters_is_idempotent_across_calls(http_server):
    _echo(http_server)
    config = make_config(
        base_url=http_server.url, pushdown_params=PUSHDOWN, schema="id BIGINT"
    )
    _module, reader = _reader(config)
    reader.pushFilters([EqualTo(("status",), "active")])
    reader.pushFilters([EqualTo(("owner_id",), 7)])
    assert reader._pushed == {"owner": "7"}
    reader.pushFilters([])
    assert reader._pushed == {}


def test_pushed_value_overrides_static_param(http_server):
    _echo(http_server)
    config = make_config(
        base_url=http_server.url,
        params={"status": "open", "kind": "post"},
        pushdown_params=PUSHDOWN,
        schema="id BIGINT",
    )
    _module, reader = _reader(config)
    reader.pushFilters([EqualTo(("status",), "closed")])
    list(reader.read(None))
    assert _queries(http_server) == [{"status": "closed", "kind": "post"}]


def test_page_partitions_probe_and_page_reads_carry_pushed_param(http_server):
    pages = {1: [{"id": 1}], 2: [{"id": 2}], 3: [{"id": 3}]}

    def route(query, headers, body):
        return 200, pages.get(int(query.get("page", "1")), []), {"X-Pages": "3"}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="page", page_param="page", page_size=1, total_pages_header="X-Pages"
        ),
        partition=PartitionConfig(strategy="pagination"),
        pushdown_params=PUSHDOWN,
        schema="id BIGINT",
    )
    _module, reader = _reader(config)
    reader.pushFilters([EqualTo(("status",), "active")])
    partitions = reader.partitions()
    assert [p.value for p in partitions] == [0, 1, 2]
    rows = [list(reader.read(p)) for p in partitions]
    assert rows == [[(1,)], [(2,)], [(3,)]]
    queries = _queries(http_server)
    assert [q["page"] for q in queries] == ["1", "1", "2", "3"]
    assert all(q["status"] == "active" for q in queries)


def test_page_partitions_fallback_read_carries_pushed_param(http_server):
    def route(query, headers, body):
        page = int(query.get("page", "1"))
        return 200, [{"id": 1}] if page == 1 else [], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="page", page_param="page", page_size=5, total_pages_header="X-Pages"
        ),
        partition=PartitionConfig(strategy="pagination"),
        pushdown_params=PUSHDOWN,
        schema="id BIGINT",
    )
    _module, reader = _reader(config)
    reader.pushFilters([EqualTo(("status",), "active")])
    partitions = reader.partitions()
    assert [p.value for p in partitions] == [None]
    list(reader.read(partitions[0]))
    assert all(q["status"] == "active" for q in _queries(http_server))


def test_page_partitions_with_incremental_send_cursor_and_pushed_param(
    http_server, tmp_path
):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [{"id": 1, "updated": "2026-01-01"}],
        {"X-Pages": "2"},
    )
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="page", page_param="page", page_size=1, total_pages_header="X-Pages"
        ),
        partition=PartitionConfig(strategy="pagination"),
        incremental=IncrementalConfig(
            mode="cursor",
            cursor_param="since",
            cursor_field="updated",
            state_path=str(tmp_path / "state.json"),
            start_value="2025-01-01",
        ),
        pushdown_params=PUSHDOWN,
        schema="id BIGINT",
    )
    _module, reader = _reader(config)
    reader.pushFilters([EqualTo(("status",), "active")])
    partitions = reader.partitions()
    assert [p.value for p in partitions] == [(0, "2025-01-01"), (1, "2025-01-01")]
    for partition in partitions:
        list(reader.read(partition))
    for query in _queries(http_server):
        assert query["status"] == "active"
        assert query["since"] == "2025-01-01"


def test_endpoint_windows_send_pushed_param_on_every_window(http_server):
    http_server.routes["/a"] = lambda q, h, b: (200, [{"id": 1}], {})
    http_server.routes["/b"] = lambda q, h, b: (200, [{"id": 2}], {})
    config = make_config(
        base_url=http_server.url,
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
        pushdown_params=PUSHDOWN,
        schema="id BIGINT",
    )
    _module, reader = _reader(config)
    reader.pushFilters([EqualTo(("status",), "active")])
    rows = [list(reader.read(p)) for p in reader.partitions()]
    assert rows == [[(1,)], [(2,)]]
    assert _queries(http_server) == [{"status": "active"}, {"status": "active"}]


def test_param_range_windows_merge_pushed_param_with_window_params(http_server):
    _echo(http_server)
    config = make_config(
        base_url=http_server.url,
        partition=PartitionConfig(
            strategy="param_range", param="region", values="eu,us"
        ),
        pushdown_params=PUSHDOWN,
        schema="id BIGINT",
    )
    _module, reader = _reader(config)
    reader.pushFilters([EqualTo(("status",), "active")])
    for partition in reader.partitions():
        list(reader.read(partition))
    assert _queries(http_server) == [
        {"region": "eu", "status": "active"},
        {"region": "us", "status": "active"},
    ]


def test_no_pushdown_code_without_mapping():
    config = make_config(
        base_url="https://x",
        pagination=PaginationConfig(
            type="page", page_param="page", page_size=5, total_pages_header="X-Pages"
        ),
        partition=PartitionConfig(strategy="pagination"),
        schema="id BIGINT",
    )
    script = generate(config)
    assert_hygiene(script)
    for needle in (
        "pushFilters",
        "PUSHDOWN_PARAMS",
        "EqualTo",
        "Iterable",
        "_pushed",
        "filterPushdown",
        "extra_params: dict[str, str]",
    ):
        assert needle not in script, needle
    assert "def _page_response(page_index: int) -> requests.Response:" in script
    assert "def _probe_total_pages() -> int | None:" in script


def test_pushdown_script_enables_the_spark_conf_and_types_the_reader():
    config = make_config(base_url="https://x", pushdown_params=PUSHDOWN)
    script = generate(config)
    assert_hygiene(script)
    assert 'spark.conf.set("spark.sql.python.filterPushdown.enabled", "true")' in script
    assert (
        "from pyspark.sql.datasource import DataSource, DataSourceReader, EqualTo, Filter"
        in script
    )
    assert "def pushFilters(self, filters: list[Filter]) -> Iterable[Filter]:" in script
    assert (
        'PUSHDOWN_PARAMS: dict[str, str] = {"status": "status", "owner_id": "owner"}'
        in script
    )
    assert "records = fetch_records(extra_params=self._pushed)" in script


def test_pushdown_rejected_for_streaming_tables():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
        pushdown_params=PUSHDOWN,
    )
    with pytest.raises(CodegenError, match="filter pushdown"):
        generate(config)


@pytest.mark.spark
def test_pushdown_end_to_end_through_spark(http_server, spark_session):
    seen = []

    def route(query, headers, body):
        seen.append(query)
        return 200, [{"id": 1, "status": query.get("status", "any")}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pushdown_params=PUSHDOWN,
        schema="id BIGINT, status STRING",
    )
    script = generate(config)
    assert_hygiene(script)
    namespace: dict = {}
    exec(compile(script, "<generated>", "exec"), namespace)  # noqa: S102
    assert spark_session.conf.get("spark.sql.python.filterPushdown.enabled") == "true"

    from pyspark.sql.functions import col

    df = spark_session.read.format("posts_source").load()
    rows = df.filter((col("status") == "active") & (col("id") > 0)).collect()
    assert [(row.id, row.status) for row in rows] == [(1, "active")]
    assert seen[-1].get("status") == "active"
