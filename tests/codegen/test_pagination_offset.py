from __future__ import annotations

from polymo.config import PaginationConfig
from tests.codegen.helpers import make_config, run_generated


def test_offset_pagination_walks_until_empty(http_server):
    def route(query, headers, body):
        offset = int(query.get("offset", "0"))
        assert query.get("limit") == "2"
        data = {0: [{"id": 1}, {"id": 2}], 2: [{"id": 3}]}.get(offset, [])
        return 200, data, {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        pagination=PaginationConfig(
            type="offset", page_size=2, limit_param="limit", offset_param="offset"
        ),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert len(http_server.log) == 3  # 2 full pages + 1 short page stops
