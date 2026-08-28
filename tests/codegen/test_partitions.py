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


def test_endpoints_windows_incremental_schema_computes_cursor_on_driver():
    # fetch_records executes on Spark executors under parallelize/flatMap for
    # windowed streams, so the module-level LAST_CURSOR mutation never reaches
    # the driver. The windowed dp table must instead derive the cursor from
    # the rows collected back on the driver.
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

    dp_section = script.split('@dp.table(name="posts")', 1)[1]
    assert "cursor_values" in dp_section
    assert "_write_state(max(cursor_values) if cursor_values else None)" in dp_section
    assert 'LAST_CURSOR["value"]' not in dp_section
    assert "# records are not tagged with their source endpoint" in script

    # LAST_CURSOR is dead module state for windowed configs: fetch_records
    # runs on executors, so a module-level LAST_CURSOR mutated there is never
    # read back by the driver (the dp table above computes the cursor from
    # collected rows instead). It must not be declared or mutated anywhere in
    # the generated script for a windowed+incremental config.
    assert "LAST_CURSOR" not in script
