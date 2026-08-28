from __future__ import annotations

from polymo.config import PaginationConfig
from tests.codegen.helpers import make_config, run_generated


def test_cursor_from_payload_path(http_server):
    def route(query, headers, body):
        cursor = query.get("cursor")
        if cursor is None:
            return 200, {"data": [{"id": 1}], "next": "abc"}, {}
        assert cursor == "abc"
        return 200, {"data": [{"id": 2}], "next": None}, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="cursor", cursor_param="cursor", cursor_path=("next",)
        ),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]


def test_cursor_next_url_path_follows_full_url(http_server):
    def route(query, headers, body):
        if query.get("p") == "2":
            return 200, {"data": [{"id": 2}]}, {}
        return (
            200,
            {"data": [{"id": 1}], "next_url": f"{http_server.url}/posts?p=2"},
            {},
        )

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(type="cursor", next_url_path=("next_url",)),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]
