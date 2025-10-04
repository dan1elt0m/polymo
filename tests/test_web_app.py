from __future__ import annotations

import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI is required for builder tests")
from fastapi.testclient import TestClient

from polymo.builder import create_app

SAMPLE_CONFIG = """\
version: 0.1
source:
  type: rest
  base_url: https://example.com
stream:
  name: posts
  path: /posts
"""


def test_validate_endpoint_success() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/validate", json={"config": SAMPLE_CONFIG})
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
    yaml_text = payload["yaml"]
    assert ("version: 0.1" in yaml_text) or ("version: '0.1'" in yaml_text)


def test_format_endpoint() -> None:
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": "https://example.com"},
        "stream": {"name": "posts", "path": "/posts"},
    }

    response = client.post("/api/format", json={"config_dict": config_dict})
    payload = response.json()

    assert response.status_code == 200
    yaml_text = payload["yaml"]
    assert ("version: 0.1" in yaml_text) or ("version: '0.1'" in yaml_text)
    assert "base_url: https://example.com" in yaml_text
