from __future__ import annotations

from polymo.config import PaginationConfig
from tests.codegen.helpers import make_config, run_generated


def test_page_pagination_stops_on_short_page(http_server):
    def route(query, headers, body):
        page = int(query.get("page", "1"))
        data = {1: [{"id": 1}, {"id": 2}], 2: [{"id": 3}]}.get(page, [])
        return 200, data, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(type="page", page_size=2, page_param="page"),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_page_pagination_respects_total_pages_path(http_server):
    def route(query, headers, body):
        page = int(query.get("page", "1"))
        return 200, {"meta": {"pages": 2}, "results": [{"p": page}]}, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="page", page_param="page", total_pages_path=("meta", "pages")
        ),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"p": 1}, {"p": 2}]
