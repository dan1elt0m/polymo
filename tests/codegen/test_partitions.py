from __future__ import annotations

from polymo.codegen import generate
from polymo.config import IncrementalConfig, PartitionConfig
from tests.codegen.helpers import assert_hygiene, make_config, run_generated


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
    # Batch dp tables now ingest through an inline PySpark custom Data
    # Source (see dp.py.jinja): each window becomes an InputPartition and
    # `_Reader.read()` runs per partition on whichever executor owns it, so
    # (unlike the old sc.parallelize().collect() version) there is never a
    # single driver-side list of rows to compute a cursor from. Instead
    # `read()` tracks its own partition-local max of `cursor_field` in a
    # plain local variable and calls `_write_state()` once it's done
    # yielding — with multiple partitions, whichever one finishes last wins
    # (batch tables re-fetch fully each run, so that only costs redundant
    # fetching, never missed data).
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
    assert 'record.get("updated")' in dp_section
    assert "_write_state(cursor)" in dp_section
    assert 'LAST_CURSOR["value"]' not in dp_section

    # LAST_CURSOR is dead module state for windowed configs: fetch_records
    # runs on executors, so a module-level LAST_CURSOR mutated there is never
    # read back by anything (the dp table above tracks the cursor locally,
    # inside read(), instead). It must not be declared or mutated anywhere
    # in the generated script for a windowed+incremental config.
    assert "LAST_CURSOR" not in script
