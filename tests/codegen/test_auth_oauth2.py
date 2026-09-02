from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from polymo.codegen import generate_core
from polymo.codegen.generator import CodegenError
from polymo.config import AuthConfig
from tests.codegen.helpers import assert_hygiene, make_config, run_generated


def test_oauth2_token_fetched_and_used(http_server):
    def token_route(query, headers, body):
        form = {k: v[-1] for k, v in parse_qs(body.decode()).items()}
        assert form["grant_type"] == "client_credentials"
        assert form["client_id"] == "cid"
        assert form["client_secret"] == "sec"
        assert form["scope"] == "read write"
        return 200, {"access_token": "tok-oauth"}, {}

    def data_route(query, headers, body):
        assert headers.get("Authorization") == "Bearer tok-oauth"
        return 200, [{"id": 1}], {}

    http_server.routes["/oauth/token"] = token_route
    http_server.routes["/posts"] = data_route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(
            type="oauth2",
            token_url=f"{http_server.url}/oauth/token",
            client_id="cid",
            scope=("read", "write"),
        ),
    )
    module = run_generated(config, override_globals={"CLIENT_SECRET": "sec"})
    assert list(module.fetch_records()) == [{"id": 1}]


def test_oauth2_lazy_token(http_server):
    # generation itself must not require a live token endpoint
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="oauth2", token_url="https://x/token", client_id="cid"),
    )
    assert "def get_token" in generate_core(config)


def test_oauth2_placeholder_and_no_secret_leak():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="oauth2",
            token_url="https://x/token",
            client_id="cid",
            client_secret="s3cret",
        ),
    )
    core = generate_core(config)
    assert 'CLIENT_SECRET: str = "REPLACE_ME"' in core
    assert "s3cret" not in core


def test_oauth2_missing_token_url_raises():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="oauth2", client_id="cid"),
    )
    with pytest.raises(CodegenError):
        generate_core(config)


def test_oauth2_missing_client_id_raises():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="oauth2", token_url="https://x/token"),
    )
    with pytest.raises(CodegenError):
        generate_core(config)


def test_oauth2_hygiene():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="oauth2",
            token_url="https://x/token",
            client_id="cid",
            scope=("read", "write"),
            audience="my-api",
        ),
    )
    assert_hygiene(generate_core(config))


def test_oauth2_extra_params_render_as_python_literals():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="oauth2",
            token_url="https://x/token",
            client_id="cid",
            extra_params={
                "include_refresh": True,
                "audience_hint": None,
                "version": 2,
            },
        ),
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert '"include_refresh": True,' in core
