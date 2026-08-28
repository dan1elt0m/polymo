from __future__ import annotations

from polymo.codegen import generate_core
from polymo.config import AuthConfig
from tests.codegen.helpers import make_config, run_generated


def test_bearer_placeholder_and_comment_present():
    config = make_config(
        base_url="https://x", auth=AuthConfig(type="bearer", token="s3cret")
    )
    core = generate_core(config)
    assert 'API_TOKEN = "REPLACE_ME"' in core
    assert "s3cret" not in core
    assert "dbutils.secrets.get" in core  # recommendation comment


def test_bearer_header_sent(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Bearer tok-123"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(base_url=http_server.url, auth=AuthConfig(type="bearer"))
    module = run_generated(config, override_globals={"API_TOKEN": "tok-123"})
    assert list(module.fetch_records()) == [{"id": 1}]
