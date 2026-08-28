from __future__ import annotations

from polymo.builder.preview import run_preview
from polymo.config import AuthConfig, PartitionConfig, PaginationConfig
from tests.codegen.helpers import make_config


def test_preview_executes_generated_code(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}, {"id": 2}], {})
    config = make_config(base_url=http_server.url)
    records, raw_pages = run_preview(config, token=None, limit=1)
    assert records == [{"id": 1}]  # limit respected
    assert raw_pages[0]["status_code"] == 200
    assert raw_pages[0]["url"].endswith("/posts")


def test_preview_injects_bearer_token(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Bearer tok-1"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(base_url=http_server.url, auth=AuthConfig(type="bearer"))
    records, _ = run_preview(config, token="tok-1", limit=5)
    assert records == [{"id": 1}]


def test_preview_windowed_config_fetches_only_first_window(http_server):
    calls = []

    def route_a(query, headers, body):
        calls.append("/a")
        return 200, [{"src": "a"}], {}

    def route_b(query, headers, body):
        calls.append("/b")
        return 200, [{"src": "b"}], {}

    http_server.routes["/a"] = route_a
    http_server.routes["/b"] = route_b

    config = make_config(
        base_url=http_server.url,
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
    )
    records, raw_pages = run_preview(config, token=None, limit=10)

    assert records == [{"src": "a"}]
    assert calls == ["/a"]
    assert all(page["url"].endswith("/a") for page in raw_pages)


def test_preview_streaming_config_uses_fetch_records(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}, {"id": 2}], {})
    config = make_config(
        base_url=http_server.url,
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    records, raw_pages = run_preview(config, token=None, limit=2)
    assert records == [{"id": 1}, {"id": 2}]
    assert raw_pages[0]["status_code"] == 200
