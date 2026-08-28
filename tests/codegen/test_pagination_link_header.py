from __future__ import annotations

from polymo.config import PaginationConfig
from tests.codegen.helpers import make_config, run_generated


def test_link_header_pagination(http_server):
    def route(query, headers, body):
        if query.get("p") == "2":
            return 200, [{"id": 2}], {}
        link = f'<{http_server.url}/posts?p=2>; rel="next"'
        return 200, [{"id": 1}], {"Link": link}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url, pagination=PaginationConfig(type="link_header")
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]
