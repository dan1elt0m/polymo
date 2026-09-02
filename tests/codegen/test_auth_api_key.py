from __future__ import annotations

from polymo.codegen import generate_core
from polymo.config import AuthConfig, PaginationConfig, PartitionConfig
from tests.codegen.helpers import assert_hygiene, make_config, run_generated


def test_api_key_header_placeholder_present():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="api_key", api_key_in="header", api_key_name="X-API-Key"),
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'API_KEY: str = "REPLACE_ME"' in core
    assert 'session.headers["X-API-Key"] = API_KEY' in core


def test_api_key_query_placeholder_present():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="api_key", api_key_in="query", api_key_name="api_key"),
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'API_KEY: str = "REPLACE_ME"' in core
    assert 'params["api_key"] = API_KEY' in core
    # header form must not be emitted for query placement
    assert "session.headers[" not in core


def test_api_key_header_sent_over_http(http_server):
    def route(query, headers, body):
        assert headers.get("X-API-Key") == "sekrit-123"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="header", api_key_name="X-API-Key"),
    )
    module = run_generated(config, override_globals={"API_KEY": "sekrit-123"})
    assert list(module.fetch_records()) == [{"id": 1}]


def test_api_key_query_param_sent_over_http(http_server):
    def route(query, headers, body):
        assert query.get("api_key") == "sekrit-123"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="query", api_key_name="api_key"),
    )
    module = run_generated(config, override_globals={"API_KEY": "sekrit-123"})
    assert list(module.fetch_records()) == [{"id": 1}]


def test_api_key_query_param_sent_with_offset_pagination(http_server):
    def route(query, headers, body):
        assert query.get("api_key") == "sekrit-123"
        return 200, [], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="query", api_key_name="api_key"),
        pagination=PaginationConfig(type="offset", offset_param="offset"),
    )
    module = run_generated(config, override_globals={"API_KEY": "sekrit-123"})
    assert list(module.fetch_records()) == []


def test_api_key_query_sent_with_cursor_pagination_next_url(http_server):
    def route(query, headers, body):
        assert query.get("api_key") == "sekrit-123"
        return 200, {"data": [{"id": 1}], "meta": {"next": None}}, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="query", api_key_name="api_key"),
        pagination=PaginationConfig(type="cursor", next_url_path=("meta", "next")),
    )
    module = run_generated(config, override_globals={"API_KEY": "sekrit-123"})
    assert list(module.fetch_records()) == [{"id": 1}]


def test_api_key_header_sent_with_link_header_pagination(http_server):
    def route(query, headers, body):
        assert headers.get("X-API-Key") == "sekrit-123"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="header", api_key_name="X-API-Key"),
        pagination=PaginationConfig(type="link_header"),
    )
    module = run_generated(config, override_globals={"API_KEY": "sekrit-123"})
    assert list(module.fetch_records()) == [{"id": 1}]


def test_api_key_hygiene_page_pagination():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="api_key", api_key_in="query", api_key_name="key"),
        pagination=PaginationConfig(type="page", page_param="page", page_size=50),
    )
    assert_hygiene(generate_core(config))


def test_api_key_streaming_fetch_page_query(http_server):
    def route(query, headers, body):
        assert query.get("api_key") == "sekrit-123"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="query", api_key_name="api_key"),
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="offset", offset_param="offset", page_size=10),
    )
    module = run_generated(config, override_globals={"API_KEY": "sekrit-123"})
    assert module.fetch_page(0) == [{"id": 1}]


def test_api_key_query_survives_windowed_extra_params(http_server):
    # Regression: the api_key query assignment used to happen BEFORE
    # `params.update(extra_params)`, so a windowed (param_range/endpoints
    # partition) fetch could silently clobber it. It's now emitted last,
    # right before the request, so extra_params can never overwrite it —
    # verified across every window a param_range partition produces.
    seen = []

    def route(query, headers, body):
        seen.append(dict(query))
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="query", api_key_name="api_key"),
        partition=PartitionConfig(
            strategy="param_range", param="region", values=("us", "eu")
        ),
    )
    module = run_generated(config, override_globals={"API_KEY": "sekrit-123"})
    assert module.WINDOWS == [
        {"extra_params": {"region": "us"}},
        {"extra_params": {"region": "eu"}},
    ]
    for window in module.WINDOWS:
        assert list(module.fetch_records(**window)) == [{"id": 1}]

    assert len(seen) == 2
    for query, expected_region in zip(seen, ("us", "eu")):
        assert query.get("api_key") == "sekrit-123"
        assert query.get("region") == expected_region


def test_api_key_streaming_fetch_page_header(http_server):
    def route(query, headers, body):
        assert headers.get("X-API-Key") == "sekrit-123"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="api_key", api_key_in="header", api_key_name="X-API-Key"),
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="offset", offset_param="offset", page_size=10),
    )
    module = run_generated(config, override_globals={"API_KEY": "sekrit-123"})
    assert module.fetch_page(0) == [{"id": 1}]
