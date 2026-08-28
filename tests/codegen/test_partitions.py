from __future__ import annotations

from polymo.config import PartitionConfig
from tests.codegen.helpers import make_config, run_generated


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
