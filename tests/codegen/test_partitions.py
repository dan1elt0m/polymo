from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest

from polymo.codegen import CodegenError, generate
from polymo.config import IncrementalConfig, PaginationConfig, PartitionConfig
from tests.codegen.helpers import (
    assert_hygiene,
    fake_schema,
    make_config,
    run_generated,
    run_generated_script,
)


def test_param_range_numeric_windows_inlined(http_server):
    seen = []

    def route(query, headers, body):
        seen.append(query.get("region"))
        return 200, [{"region": query.get("region")}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        partition=PartitionConfig(
            strategy="param_range",
            param="region",
            range_start=1,
            range_end=3,
            range_step=1,
            range_kind="numeric",
        ),
    )
    module = run_generated(config)
    assert module.WINDOWS == [
        {"extra_params": {"region": "1"}},
        {"extra_params": {"region": "2"}},
        {"extra_params": {"region": "3"}},
    ]
    _ = [r for w in module.WINDOWS for r in module.fetch_records(**w)]
    assert sorted(seen) == ["1", "2", "3"]


def test_endpoints_windows(http_server):
    http_server.routes["/a"] = lambda q, h, b: (200, [{"src": "a"}], {})
    http_server.routes["/b"] = lambda q, h, b: (200, [{"src": "b"}], {})
    config = make_config(
        base_url=http_server.url,
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
    )
    module = run_generated(config)
    records = [r for w in module.WINDOWS for r in module.fetch_records(**w)]
    assert records == [{"src": "a"}, {"src": "b"}]


def test_endpoints_windows_incremental_schema_tracks_cursor_per_partition():
    # Each window becomes an InputPartition and `_Reader.read()` runs per
    # partition on whichever executor owns it, so there is never a single
    # driver-side list of rows to compute a cursor from. Instead `read()`
    # tracks its own partition-local max of the cursor field and commits it
    # through the monotone `_write_state()` once done yielding — whichever
    # order the partitions finish in, the stored cursor ends at the max.
    config = make_config(
        base_url="https://api.example.com",
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
        schema="id INT",
    )
    script = generate(config)
    assert_hygiene(script)

    dp_section = script.split("class RestSource(DataSource):", 1)[1]
    assert "def partitions(self) -> list[InputPartition]:" in dp_section
    assert "InputPartition(index) for index in range(len(WINDOWS))" in dp_section
    assert "fetch_records(**WINDOWS[partition.value])" in dp_section
    assert "value = _cursor_of(record)" in dp_section
    assert "_write_state(cursor)" in dp_section

    # no module-level cursor accumulator anywhere: fetch_records runs on
    # executors, so module state mutated there could never be read back.
    assert "LAST_CURSOR" not in script


# --- pagination strategy: one partition per page -----------------------------
# Restores the 0.x `_plan_pagination_partitions` planner as generated code:
# the driver probes the first page once, resolves the page count from the
# total hints (path before header, pages before records) and hands Spark one
# InputPartition per page; each partition then fetches exactly its page.


def _page_requests(http_server, param: str) -> list:
    """The `param` query value of every request the mock server saw, in order."""
    values = []
    for _method, path, _headers in http_server.log:
        query = parse_qs(urlparse(path).query)
        values.append(query.get(param, [None])[0])
    return values


def _fanout_config(http_server, **pagination):
    fields = dict(type="page", page_param="page", limit_param="per_page", page_size=2)
    fields.update(pagination)
    return make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(**fields),
        partition=PartitionConfig(strategy="pagination"),
        schema="id BIGINT",
    )


def _paged_route(pages: dict, *, meta=None, headers=None):
    def route(query, request_headers, body):
        page = int(query.get("page", "1"))
        records = pages.get(page, [])
        payload = records if meta is None else {"meta": meta, "data": records}
        return 200, payload, dict(headers or {})

    return route


@pytest.mark.parametrize(
    "pagination,expected",
    [
        # total_pages_path wins over the header, and pages win over records
        (
            dict(
                total_pages_path=("meta", "pages"),
                total_pages_header="X-Pages",
                total_records_path=("meta", "total"),
                total_records_header="X-Total",
            ),
            3,
        ),
        (dict(total_pages_header="X-Pages", total_records_path=("meta", "total")), 4),
        # records -> ceil(total / page_size) with page_size=2
        (dict(total_records_path=("meta", "total")), 5),
        (dict(total_records_header="X-Total"), 6),
        # a path that resolves to nothing falls through to the header
        (dict(total_pages_path=("meta", "missing"), total_pages_header="X-Pages"), 4),
        (
            dict(
                total_records_path=("meta", "missing"), total_records_header="X-Total"
            ),
            6,
        ),
    ],
    ids=[
        "path-over-header-pages-over-records",
        "header-pages-over-path-records",
        "records-path",
        "records-header",
        "pages-path-missing-falls-to-header",
        "records-path-missing-falls-to-header",
    ],
)
def test_pagination_fanout_probe_resolves_total_pages_with_0x_precedence(
    http_server, pagination, expected
):
    http_server.routes["/posts"] = _paged_route(
        {1: [{"id": 1}, {"id": 2}]},
        meta={"pages": 3, "total": 9},
        headers={"X-Pages": "4", "X-Total": "11"},
    )
    module = run_generated(_fanout_config(http_server, **pagination))
    assert module._probe_total_pages() == expected
    # the probe is exactly one request, for the first page
    assert _page_requests(http_server, "page") == ["1"]


@pytest.mark.parametrize("bad", ["0", "-2", "abc", ""])
def test_pagination_fanout_probe_ignores_non_positive_hints(http_server, bad):
    http_server.routes["/posts"] = _paged_route(
        {1: [{"id": 1}]}, headers={"X-Pages": bad}
    )
    module = run_generated(_fanout_config(http_server, total_pages_header="X-Pages"))
    assert module._probe_total_pages() is None


def test_pagination_fanout_one_partition_per_page_each_fetching_one_page(
    http_server,
):
    pages = {1: [{"id": 1}, {"id": 2}], 2: [{"id": 3}, {"id": 4}], 3: [{"id": 5}]}
    http_server.routes["/posts"] = _paged_route(pages, headers={"X-Pages": "3"})
    module = run_generated_script(
        _fanout_config(http_server, total_pages_header="X-Pages")
    )
    reader = module._Reader(fake_schema("id"))

    partitions = reader.partitions()
    assert [p.value for p in partitions] == [0, 1, 2]
    assert _page_requests(http_server, "page") == ["1"]

    rows = {p.value: list(reader.read(p)) for p in partitions}
    assert rows == {0: [(1,), (2,)], 1: [(3,), (4,)], 2: [(5,)]}
    # probe + exactly one request per partition, nothing else
    assert _page_requests(http_server, "page") == ["1", "1", "2", "3"]
    assert _page_requests(http_server, "per_page") == ["2"] * 4


def test_pagination_fanout_falls_back_to_one_sequential_partition_when_unknown(
    http_server,
):
    pages = {1: [{"id": 1}, {"id": 2}], 2: [{"id": 3}]}
    http_server.routes["/posts"] = _paged_route(pages)
    module = run_generated_script(
        _fanout_config(http_server, total_pages_header="X-Pages")
    )
    reader = module._Reader(fake_schema("id"))

    partitions = reader.partitions()
    assert [p.value for p in partitions] == [None]

    rows = list(reader.read(partitions[0]))
    assert rows == [(1,), (2,), (3,)]
    # probe, then the whole stream sequentially until the empty page 3
    assert _page_requests(http_server, "page") == ["1", "1", "2", "3"]


def test_pagination_fanout_single_page_total_reads_sequentially(http_server):
    http_server.routes["/posts"] = _paged_route(
        {1: [{"id": 1}]}, headers={"X-Pages": "1"}
    )
    module = run_generated_script(
        _fanout_config(http_server, total_pages_header="X-Pages")
    )
    reader = module._Reader(fake_schema("id"))
    partitions = reader.partitions()
    assert [p.value for p in partitions] == [None]
    assert list(reader.read(partitions[0])) == [(1,)]


def test_pagination_fanout_offset_partitions_use_start_offset_and_page_size(
    http_server,
):
    def route(query, headers, body):
        offset = int(query["offset"])
        return 200, {"meta": {"total": 7}, "data": [{"id": offset}]}, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="offset",
            offset_param="offset",
            limit_param="limit",
            page_size=3,
            start_offset=10,
            total_records_path=("meta", "total"),
        ),
        partition=PartitionConfig(strategy="pagination"),
        schema="id BIGINT",
    )
    script = generate(config)
    assert 'params["offset"] = 10 + page_index * 3' in script
    module = run_generated_script(config)
    reader = module._Reader(fake_schema("id"))

    partitions = reader.partitions()
    assert [p.value for p in partitions] == [0, 1, 2]
    rows = [list(reader.read(p)) for p in partitions]
    assert rows == [[(10,)], [(13,)], [(16,)]]
    assert _page_requests(http_server, "offset") == ["10", "10", "13", "16"]
    assert _page_requests(http_server, "limit") == ["3"] * 4


def test_pagination_fanout_start_page_zero(http_server):
    http_server.routes["/posts"] = _paged_route(
        {0: [{"id": 0}], 1: [{"id": 1}]}, headers={"X-Pages": "2"}
    )
    config = _fanout_config(http_server, start_page=0, total_pages_header="X-Pages")
    assert 'params["page"] = page_index\n' in generate(config)
    module = run_generated_script(config)
    reader = module._Reader(fake_schema("id"))
    partitions = reader.partitions()
    assert [list(reader.read(p)) for p in partitions] == [[(0,)], [(1,)]]
    assert _page_requests(http_server, "page") == ["0", "0", "1"]


@pytest.mark.parametrize(
    "pagination,partition",
    [
        # no total hint: nothing to plan from
        (
            PaginationConfig(type="page", page_param="page", page_size=2),
            PartitionConfig(strategy="pagination"),
        ),
        # no page_size: page windows can't be sized
        (
            PaginationConfig(type="page", page_param="page", total_pages_header="X"),
            PartitionConfig(strategy="pagination"),
        ),
        # cursor pagination has no page arithmetic to fan out over
        (
            PaginationConfig(
                type="cursor", cursor_param="after", cursor_path=("next",)
            ),
            PartitionConfig(strategy="pagination"),
        ),
        # hints alone, without the strategy, only trim the sequential loop
        (
            PaginationConfig(
                type="page", page_param="page", page_size=2, total_pages_header="X"
            ),
            PartitionConfig(),
        ),
    ],
    ids=["no-hints", "no-page-size", "cursor-pagination", "strategy-none"],
)
def test_pagination_fanout_not_applicable_generates_sequential_code_only(
    pagination, partition
):
    config = make_config(
        base_url="https://x", pagination=pagination, partition=partition
    )
    script = generate(config)
    assert_hygiene(script)
    assert "_probe_total_pages" not in script
    assert "_page_response" not in script
    assert "fetch_page" not in script
    assert "_positive_int" not in script
    assert "InputPartition" not in script
    assert "import math" not in script


def test_pagination_fanout_rejected_for_streaming_tables():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(
            type="page", page_param="page", page_size=2, total_pages_header="X"
        ),
        partition=PartitionConfig(strategy="pagination"),
    )
    with pytest.raises(CodegenError, match="partition strategies"):
        generate(config)


def _incremental_fanout_config(http_server, state_file):
    return make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="page",
            page_param="page",
            limit_param="per_page",
            page_size=2,
            total_pages_header="X-Pages",
        ),
        partition=PartitionConfig(strategy="pagination"),
        incremental=IncrementalConfig(
            mode="cursor",
            cursor_param="since",
            cursor_field="updated",
            state_path=str(state_file),
            start_value="2025-12-31",
        ),
        schema="id BIGINT, updated STRING",
    )


def test_pagination_fanout_with_incremental_applies_cursor_and_commits_global_max(
    http_server, tmp_path
):
    pages = {
        1: [{"id": 1, "updated": "2026-01-01"}, {"id": 2, "updated": "2026-03-01"}],
        2: [{"id": 3, "updated": "2026-02-01"}, {"id": 4, "updated": "2026-05-01"}],
        3: [{"id": 5, "updated": "2026-04-01"}],
    }
    http_server.routes["/posts"] = _paged_route(pages, headers={"X-Pages": "3"})
    state_file = tmp_path / "state.json"
    module = run_generated_script(_incremental_fanout_config(http_server, state_file))
    reader = module._Reader(fake_schema("id", "updated"))

    partitions = reader.partitions()
    assert [p.value for p in partitions] == [
        (0, "2025-12-31"),
        (1, "2025-12-31"),
        (2, "2025-12-31"),
    ]
    # the probe already sent the seed cursor
    assert _page_requests(http_server, "since") == ["2025-12-31"]

    # executors finish in any order; each carries the cursor the driver
    # planned with, so a partition that starts after another committed still
    # fetches the same page set the probe counted
    for partition in reversed(partitions):
        list(reader.read(partition))
    assert _page_requests(http_server, "page") == ["1", "3", "2", "1"]
    assert _page_requests(http_server, "since") == ["2025-12-31"] * 4
    assert module._read_state() == "2026-05-01"

    # a second run plans from the committed cursor
    reader = module._Reader(fake_schema("id", "updated"))
    assert reader.partitions()[0].value == (0, "2026-05-01")


def test_pagination_fanout_with_incremental_fallback_partition(http_server, tmp_path):
    http_server.routes["/posts"] = _paged_route(
        {1: [{"id": 1, "updated": "2026-01-01"}]}
    )
    state_file = tmp_path / "state.json"
    module = run_generated_script(_incremental_fanout_config(http_server, state_file))
    reader = module._Reader(fake_schema("id", "updated"))
    partitions = reader.partitions()
    assert [p.value for p in partitions] == [(None, "2025-12-31")]
    assert list(reader.read(partitions[0])) == [(1, "2026-01-01")]
    assert module._read_state() == "2026-01-01"


@pytest.mark.spark
def test_pagination_fanout_with_incremental_end_to_end_through_spark(
    http_server, spark_session, tmp_path
):
    pages = {
        1: [{"id": 1, "updated": "2026-01-01"}, {"id": 2, "updated": "2026-03-01"}],
        2: [{"id": 3, "updated": "2026-02-01"}, {"id": 4, "updated": "2026-05-01"}],
        3: [{"id": 5, "updated": "2026-04-01"}],
    }
    http_server.routes["/posts"] = _paged_route(pages, headers={"X-Pages": "3"})
    state_file = tmp_path / "state.json"
    config = _incremental_fanout_config(http_server, state_file)
    script = generate(config)
    assert_hygiene(script)
    namespace: dict = {}
    exec(compile(script, "<generated>", "exec"), namespace)  # noqa: S102

    df = spark_session.read.format("posts_source").load()
    assert df.rdd.getNumPartitions() == 3
    assert sorted(row.id for row in df.collect()) == [1, 2, 3, 4, 5]
    # driver probe + one request per partition, all carrying the seed cursor
    assert sorted(_page_requests(http_server, "page")) == ["1", "1", "2", "3"]
    assert _page_requests(http_server, "since") == ["2025-12-31"] * 4
    assert namespace["_read_state"]() == "2026-05-01"
