from __future__ import annotations

import json
import sys

from polymo.builder.preview import run_preview
from polymo.config import (
    AuthConfig,
    ErrorHandlerConfig,
    IncrementalConfig,
    PaginationConfig,
    PartitionConfig,
    SecretRef,
    UcSecretRef,
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


# --- incremental state --------------------------------------------------------
# The preview drives `fetch_records()` directly, which only ever *reads* the
# cursor (`_Reader.read()` is what commits it), and it does so against a
# throwaway state path under a temp dir rather than the user's real one.


def _incremental(**overrides):
    fields = dict(mode="cursor", cursor_param="since", cursor_field="updated")
    fields.update(overrides)
    return IncrementalConfig(**fields)


def test_preview_incremental_config_writes_no_state_file(
    http_server, tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    seen = []

    def route(query, headers, body):
        seen.append(query.get("since"))
        return 200, [{"id": 1, "updated": "2026-01-01"}], {}

    http_server.routes["/posts"] = route
    config = make_config(base_url=http_server.url, incremental=_incremental())
    records, _, error = run_preview(config, token=None, limit=5)
    assert records == [{"id": 1, "updated": "2026-01-01"}]
    assert error is None
    assert seen == [None]
    assert list(tmp_path.iterdir()) == []


def test_preview_incremental_seeds_cursor_from_start_value_only(http_server, tmp_path):
    seen = []

    def route(query, headers, body):
        seen.append(query.get("since"))
        return 200, [{"id": 1, "updated": "2026-03-01"}], {}

    http_server.routes["/posts"] = route
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps(
            {"streams": {f"posts@{http_server.url}": {"cursor_value": "2026-02-01"}}}
        )
    )
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path=str(state_file), start_value="2025-01-01"),
    )
    records, _, error = run_preview(config, token=None, limit=5)
    assert error is None
    assert records == [{"id": 1, "updated": "2026-03-01"}]
    # the real state file is neither read (2026-02-01 was never sent) nor
    # touched by the preview
    assert seen == ["2025-01-01"]
    assert json.loads(state_file.read_text())["streams"][
        f"posts@{http_server.url}"
    ] == {"cursor_value": "2026-02-01"}


def test_preview_remote_state_path_works_without_fsspec(http_server, monkeypatch):
    monkeypatch.setitem(sys.modules, "fsspec", None)
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}], {})
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path="s3://team/state/posts.json"),
    )
    records, _, error = run_preview(config, token=None, limit=5)
    assert error is None
    assert records == [{"id": 1}]


# --- Databricks secret-scope references -----------------------------------
#
# The generated `API_TOKEN: str = _dbx_secret(...)` assignment executes at
# module level during `exec` and would raise outside Databricks (no active
# Spark session). `run_preview` must source-substitute it to a literal
# before exec — a real token when the preview supplies one, else the same
# "REPLACE_ME" dummy the plain-placeholder path already uses.


def test_preview_secret_ref_with_token_sends_it_to_server(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Bearer real-token"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(
            type="bearer", secret=SecretRef(scope="my-scope", key="my-key")
        ),
    )
    records, _, error = run_preview(config, token="real-token", limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_secret_ref_without_token_sends_dummy_and_succeeds(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Bearer REPLACE_ME"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(
            type="bearer", secret=SecretRef(scope="my-scope", key="my-key")
        ),
    )
    records, _, error = run_preview(config, token=None, limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_api_key_secret_ref_with_token(http_server):
    def route(query, headers, body):
        assert headers.get("X-API-Key") == "key-1"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(
            type="api_key",
            api_key_in="header",
            api_key_name="X-API-Key",
            secret=SecretRef(scope="kv-scope", key="api-key"),
        ),
    )
    records, _, error = run_preview(config, token="key-1", limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_oauth2_secret_ref_with_token(http_server):
    calls = {"token": 0}

    def token_route(query, headers, body):
        calls["token"] += 1
        return 200, {"access_token": "tok-abc"}, {}

    def data_route(query, headers, body):
        assert headers.get("Authorization") == "Bearer tok-abc"
        return 200, [{"id": 1}], {}

    http_server.routes["/token"] = token_route
    http_server.routes["/posts"] = data_route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(
            type="oauth2",
            token_url=f"{http_server.url}/token",
            client_id="cid",
            secret=SecretRef(scope="kv-scope", key="client-secret"),
        ),
    )
    # CLIENT_SECRET is only consumed by the token-request body, so no route
    # asserts on it directly here; the important bit is exec doesn't raise
    # and the real token request completes successfully.
    records, _, error = run_preview(config, token="whatever-session-token", limit=5)
    assert records == [{"id": 1}]
    assert error is None
    assert calls["token"] == 1


def test_preview_option_secret_ref_has_no_override_and_sends_dummy(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Basic REPLACE_ME"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        headers={"Authorization": "Basic {{ options.api_key_b64 }}"},
        option_secrets={"api_key_b64": SecretRef(scope="kv-scope", key="b64-key")},
    )
    records, _, error = run_preview(config, token=None, limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_option_secret_ref_unaffected_by_unrelated_token(http_server):
    """A bearer preview token must not leak into an OPT_* secret-ref slot."""

    def route(query, headers, body):
        assert headers.get("Authorization") == "Basic REPLACE_ME"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        headers={"Authorization": "Basic {{ options.api_key_b64 }}"},
        option_secrets={"api_key_b64": SecretRef(scope="kv-scope", key="b64-key")},
    )
    records, _, error = run_preview(config, token="some-bearer-token", limit=5)
    assert records == [{"id": 1}]
    assert error is None


# --- Unity Catalog service-credential secret references (`_uc_secret`) ----
# Mirrors the `_dbx_secret` tests above: a module-level `_uc_secret(...)`
# call executes during `exec` and would raise outside Databricks (no active
# Spark session / no dbutils / no Key Vault access) — `run_preview` must
# source-substitute it the same way it does `_dbx_secret(...)`.


def _uc_ref() -> UcSecretRef:
    return UcSecretRef(
        credential="kv-cred",
        vault_url="https://my-vault.vault.azure.net/",
        secret_name="api-token",
    )


def test_preview_uc_secret_ref_with_token_sends_it_to_server(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Bearer real-token"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="bearer", uc_secret=_uc_ref()),
    )
    records, _, error = run_preview(config, token="real-token", limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_uc_secret_ref_without_token_sends_dummy_and_succeeds(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Bearer REPLACE_ME"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(type="bearer", uc_secret=_uc_ref()),
    )
    records, _, error = run_preview(config, token=None, limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_api_key_uc_secret_ref_with_token(http_server):
    def route(query, headers, body):
        assert headers.get("X-API-Key") == "key-1"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(
            type="api_key",
            api_key_in="header",
            api_key_name="X-API-Key",
            uc_secret=_uc_ref(),
        ),
    )
    records, _, error = run_preview(config, token="key-1", limit=5)
    assert records == [{"id": 1}]
    assert error is None


def test_preview_oauth2_uc_secret_ref_with_token(http_server):
    calls = {"token": 0}

    def token_route(query, headers, body):
        calls["token"] += 1
        return 200, {"access_token": "tok-abc"}, {}

    def data_route(query, headers, body):
        assert headers.get("Authorization") == "Bearer tok-abc"
        return 200, [{"id": 1}], {}

    http_server.routes["/token"] = token_route
    http_server.routes["/posts"] = data_route
    config = make_config(
        base_url=http_server.url,
        auth=AuthConfig(
            type="oauth2",
            token_url=f"{http_server.url}/token",
            client_id="cid",
            uc_secret=_uc_ref(),
        ),
    )
    records, _, error = run_preview(config, token="whatever-session-token", limit=5)
    assert records == [{"id": 1}]
    assert error is None
    assert calls["token"] == 1
