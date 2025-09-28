from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from polymo.builder import create_app

SAMPLE_CONFIG = """\
version: 0.1
source:
  type: rest
  base_url: https://example.com
streams:
  - name: posts
    path: /posts
"""


def test_validate_endpoint_success() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/validate", json={"config": SAMPLE_CONFIG})
    payload = response.json()

    assert response.status_code == 200
    assert payload["valid"] is True
    assert payload["streams"] == ["posts"]


@pytest.mark.parametrize("stream_name", [None, "posts"])
def test_sample_endpoint(monkeypatch: pytest.MonkeyPatch, stream_name: str | None) -> None:
    app = create_app()
    client = TestClient(app)

    def fake_collect(config, stream, limit):  # type: ignore[unused-argument]
        return [{"id": 1}, {"id": 2}][:limit]

    monkeypatch.setattr("polymo.builder.app._collect_records", fake_collect)

    payload = {"config": SAMPLE_CONFIG, "limit": 1}
    if stream_name:
        payload["stream"] = stream_name

    response = client.post("/api/sample", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["records"] == [{"id": 1}]


def test_validate_with_config_dict() -> None:
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": "https://example.com"},
        "streams": [{"name": "posts", "path": "/posts"}],
    }

    response = client.post("/api/validate", json={"config_dict": config_dict})
    payload = response.json()

    assert response.status_code == 200
    assert payload["valid"] is True
    assert payload["streams"] == ["posts"]
    assert payload["config"]["source"]["base_url"] == "https://example.com"
    yaml_text = payload["yaml"]
    assert ("version: 0.1" in yaml_text) or ("version: '0.1'" in yaml_text)


def test_format_endpoint() -> None:
    app = create_app()
    client = TestClient(app)

    config_dict = {
        "version": "0.1",
        "source": {"type": "rest", "base_url": "https://example.com"},
        "streams": [{"name": "posts", "path": "/posts"}],
    }

    response = client.post("/api/format", json={"config_dict": config_dict})
    payload = response.json()

    assert response.status_code == 200
    yaml_text = payload["yaml"]
    assert ("version: 0.1" in yaml_text) or ("version: '0.1'" in yaml_text)
    assert "base_url: https://example.com" in yaml_text
