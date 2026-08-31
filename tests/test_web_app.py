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


def test_generate_rejects_invalid_config() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/generate", json={"config_dict": {"version": "0.1"}})

    assert response.status_code == 400


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
