from __future__ import annotations

from polymo.builder.preview import run_preview
from polymo.config import (
    AuthConfig,
    ErrorHandlerConfig,
    PaginationConfig,
    PartitionConfig,
)
from tests.codegen.helpers import make_config


def test_preview_executes_generated_code(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}, {"id": 2}], {})
    config = make_config(base_url=http_server.url)
    records, raw_pages, error = run_preview(config, token=None, limit=1)
    assert records == [{"id": 1}]  # limit respected
    assert raw_pages[0]["status_code"] == 200
    assert raw_pages[0]["url"].endswith("/posts")
    assert error is None


def test_preview_injects_bearer_token(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Bearer tok-1"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(base_url=http_server.url, auth=AuthConfig(type="bearer"))
    records, _, error = run_preview(config, token="tok-1", limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_injects_api_key_header(http_server):
    def route(query, headers, body):
        assert headers.get("X-API-Key") == "key-1"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="header", api_key_name="X-API-Key"),
    )
    records, _, error = run_preview(config, token="key-1", limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_injects_api_key_query(http_server):
    def route(query, headers, body):
        assert query.get("api_key") == "key-1"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="query", api_key_name="api_key"),
    )
    records, _, error = run_preview(config, token="key-1", limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_windowed_config_blends_across_windows(http_server):
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
    records, raw_pages, error = run_preview(config, token=None, limit=10)

    assert records == [{"src": "a"}, {"src": "b"}]
    assert calls == ["/a", "/b"]
    assert {page["url"].rsplit("/", 1)[-1] for page in raw_pages} == {"a", "b"}
    assert error is None


def test_preview_windowed_config_stops_early_once_limit_reached(http_server):
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
    records, raw_pages, error = run_preview(config, token=None, limit=1)

    assert records == [{"src": "a"}]
    assert calls == ["/a"]
    assert all(page["url"].endswith("/a") for page in raw_pages)
    assert error is None


def test_preview_xml_config_parses_records(http_server):
    body = (
        "<contacts>"
        '<contact id="7"><email>a@b.nl</email></contact>'
        '<contact id="8"><email>c@d.nl</email></contact>'
        "</contacts>"
    )
    http_server.routes["/contacts"] = lambda q, h, b: (
        200,
        body,
        {"Content-Type": "application/vnd.maileon.api+xml"},
    )
    config = make_config(
        base_url=http_server.url,
        name="contacts",
        path="/contacts",
        response_format="xml",
        xml_record_path=".//contact",
    )
    records, raw_pages, error = run_preview(config, token=None, limit=10)
    assert records == [
        {"@id": "7", "email": "a@b.nl"},
        {"@id": "8", "email": "c@d.nl"},
    ]
    assert raw_pages[0]["status_code"] == 200
    # `_request`'s recording wrapper falls back to `response.text` when the
    # body isn't JSON, so the raw XML string should show up unmodified here.
    assert raw_pages[0]["payload"] == body
    assert error is None


def test_preview_streaming_config_uses_fetch_records(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}, {"id": 2}], {})
    config = make_config(
        base_url=http_server.url,
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    records, raw_pages, error = run_preview(config, token=None, limit=2)
    assert records == [{"id": 1}, {"id": 2}]
    assert raw_pages[0]["status_code"] == 200
    assert error is None


def test_preview_keeps_partial_raw_pages_on_mid_stream_failure(http_server):
    def route(query, headers, body):
        if query.get("page") == "1":
            return 200, [{"id": 1}], {}
        return 500, {"error": "boom"}, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(type="page", page_param="page", start_page=1),
        error_handler=ErrorHandlerConfig(
            max_retries=0, retry_on_timeout=False, retry_on_connection_errors=False
        ),
    )
    records, raw_pages, error = run_preview(config, token=None, limit=100)

    # The first page succeeded before the second page's request failed with
    # retries exhausted — both the records and the raw page from that first
    # successful fetch must survive the later failure.
    assert records == [{"id": 1}]
    assert any(page["status_code"] == 200 for page in raw_pages)
    assert error is not None
