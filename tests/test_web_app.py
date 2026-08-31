from __future__ import annotations

from importlib import resources

import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI is required for builder tests")
from fastapi.testclient import TestClient  # noqa: E402

from polymo.builder import create_app  # noqa: E402

SAMPLE_CONFIG_DICT = {
    "version": "0.1",
    "source": {"type": "rest", "base_url": "https://example.com"},
    "stream": {"name": "posts", "path": "/posts"},
}


def test_validate_endpoint_success() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/validate", json={"config_dict": SAMPLE_CONFIG_DICT})
    payload = response.json()

    assert response.status_code == 200
    assert payload["stream"] == "posts"


def test_validate_with_config_dict() -> None:
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": "https://example.com"},
        "stream": {"name": "posts", "path": "/posts"},
    }

    response = client.post("/api/validate", json={"config_dict": config_dict})
    payload = response.json()

    assert response.status_code == 200
    assert payload["valid"] is True
    assert payload["stream"] == "posts"
    assert payload["config"]["source"]["base_url"] == "https://example.com"
    assert "yaml" not in payload


def test_yaml_payload_rejected() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/validate", json={"config": "version: 0.1"})

    assert response.status_code == 422


def test_index_serves_built_ui_bundle() -> None:
    """GET / must serve the built React app, and that bundle must be the new,
    codegen-era UI — not a stale build from before /api/generate existed."""
    app = create_app()
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200

    static_path = resources.files("polymo.builder").joinpath("static", "main.js")
    main_js = static_path.read_text(encoding="utf-8")
    assert "/api/generate" in main_js


def test_generate_returns_script() -> None:
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": "https://example.com"},
        "stream": {"name": "posts", "path": "/posts"},
    }

    response = client.post("/api/generate", json={"config_dict": config_dict})
    payload = response.json()

    assert response.status_code == 200
    assert payload["stream"] == "posts"
    assert "from pyspark import pipelines as dp" in payload["script"]
    assert "import polymo" not in payload["script"]


def test_generate_uses_explicit_stream_name_as_table_name() -> None:
    """Feature: builder UI 'Table name' field. When `stream.name` is set in
    the config dict it becomes the dp table name, overriding the
    path-derived default (which for `/data/records` would be
    `data_records`, not `my_table`)."""
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": "https://example.com"},
        "stream": {"name": "my_table", "path": "/data/records"},
    }

    response = client.post("/api/generate", json={"config_dict": config_dict})
    payload = response.json()

    assert response.status_code == 200
    assert payload["stream"] == "my_table"
    assert '@dp.table(name="my_table")' in payload["script"]


def test_generate_rejects_invalid_config() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/generate", json={"config_dict": {"version": "0.1"}})

    assert response.status_code == 400


def test_generate_rejects_codegen_invalid_config() -> None:
    """A config can be parse-valid (passes `parse_config`) yet still be
    rejected at the codegen stage: streaming without a schema parses fine
    but `generate()` refuses it. `/api/generate` should surface that as a
    400 with the codegen error message in `detail`, not a 500."""
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": "https://example.com"},
        "stream": {"name": "posts", "path": "/posts", "streaming": True},
    }

    response = client.post("/api/generate", json={"config_dict": config_dict})
    payload = response.json()

    assert response.status_code == 400
    assert "streaming" in payload["detail"]


def test_generate_endpoint_no_longer_crashes_on_unresolved_option() -> None:
    """Regression pin: /api/generate passes no `options`, so a config whose
    headers reference `{{ options.<name> }}` (e.g. the builder's api_key
    auth, or a hand-written `Authorization: Basic {{ options.api_key_b64 }}`
    header) used to fail template rendering. It must now generate a script
    with an `OPT_*` placeholder variable instead."""
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {
            "type": "rest",
            "base_url": "https://api.maileon.com/1.0",
            "auth": {"type": "none"},
        },
        "stream": {
            "name": "contacts",
            "path": "/contacts",
            "headers": {
                "Authorization": "Basic {{ options.api_key_b64 }}",
                "Accept": "application/vnd.maileon.api+xml",
            },
            "response_format": "xml",
            "xml_record_path": ".//contact",
        },
    }

    response = client.post("/api/generate", json={"config_dict": config_dict})
    payload = response.json()

    assert response.status_code == 200
    assert 'OPT_API_KEY_B64 = "REPLACE_ME"' in payload["script"]
    assert 'f"Basic {OPT_API_KEY_B64}"' in payload["script"]


def test_sample_endpoint_executes_generated_code(http_server) -> None:
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}, {"id": 2}], {})
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": http_server.url},
        "stream": {"name": "posts", "path": "/posts"},
    }

    response = client.post("/api/sample", json={"config_dict": config_dict, "limit": 5})
    payload = response.json()

    assert response.status_code == 200
    assert payload["stream"] == "posts"
    assert payload["records"] == [{"id": 1}, {"id": 2}]
    assert payload["rest_error"] is None
    assert payload["raw_pages"][0]["status_code"] == 200
    assert payload["raw_pages"][0]["url"].endswith("/posts")
    assert payload["dtypes"]


def test_sample_endpoint_reports_rest_error() -> None:
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": "http://127.0.0.1:1"},
        "stream": {
            "name": "posts",
            "path": "/posts",
            "error_handler": {
                "max_retries": 0,
                "retry_on_connection_errors": False,
                "retry_on_timeout": False,
            },
        },
    }

    response = client.post("/api/sample", json={"config_dict": config_dict, "limit": 5})
    payload = response.json()

    assert response.status_code == 200
    assert payload["records"] == []
    assert payload["dtypes"] == []
    assert payload["rest_error"]


def test_sample_endpoint_inlines_supplied_options_for_preview(http_server) -> None:
    """/api/sample (unlike /api/generate) forwards `payload.options` into
    `parse_config(..., options=...)`, so an `{{ options.* }}` reference
    resolves to the real supplied value for the preview instead of falling
    back to an `OPT_*` placeholder that defaults to "REPLACE_ME"."""

    def route(query, headers, body):
        assert headers.get("Authorization") == "Basic realsecret"
        return 200, [{"id": 1}], {}

    http_server.routes["/contacts"] = route
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": http_server.url},
        "stream": {
            "name": "contacts",
            "path": "/contacts",
            "headers": {"Authorization": "Basic {{ options.api_key_b64 }}"},
        },
    }

    response = client.post(
        "/api/sample",
        json={
            "config_dict": config_dict,
            "options": {"api_key_b64": "realsecret"},
            "limit": 5,
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["rest_error"] is None
    assert payload["records"] == [{"id": 1}]
    assert payload["raw_pages"][0]["status_code"] == 200
