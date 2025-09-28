from __future__ import annotations

from typing import Any, Callable, List

import httpx
import pytest

from polymo.config import AuthConfig, PaginationConfig, StreamConfig
from polymo.rest_client import RestClient

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture
def install_transport(monkeypatch: pytest.MonkeyPatch) -> Callable[[Handler], List[httpx.Request]]:
    calls: List[httpx.Request] = []

    original_client = httpx.Client

    def factory(handler: Handler) -> List[httpx.Request]:
        transport = httpx.MockTransport(lambda request: _record(handler, request, calls))

        def client_factory(*args: Any, **kwargs: Any) -> httpx.Client:
            kwargs.setdefault("transport", transport)
            return original_client(*args, **kwargs)

        monkeypatch.setattr("polymo.rest_client.httpx.Client", client_factory)
        return calls

    return factory


def _record(handler: Handler, request: httpx.Request, calls: List[httpx.Request]) -> httpx.Response:
    calls.append(request)
    return handler(request)


def test_fetch_records_paginated(install_transport: Callable[[Handler], List[httpx.Request]]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/page1":
            headers = {"Link": "</page2>; rel=\"next\""}
            return httpx.Response(200, json=[{"id": 1}], headers=headers)
        if request.url.path == "/page2":
            return httpx.Response(200, json=[{"id": 2}])
        pytest.fail(f"Unexpected URL: {request.url}")

    calls = install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/page1",
        pagination=PaginationConfig(type="link_header"),
    )

    client = RestClient(base_url="https://example.com", auth=AuthConfig())
    pages = list(client.fetch_records(stream))

    assert pages == [[{"id": 1}], [{"id": 2}]]
    assert [req.url.path for req in calls] == ["/page1", "/page2"]


def test_fetch_records_normalises_wrapped_payload(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": 5}]})

    install_transport(handler)

    stream = StreamConfig(name="sample", path="/page1")
    client = RestClient(base_url="https://example.com", auth=AuthConfig())

    pages = list(client.fetch_records(stream))

    assert pages == [[{"id": 5}]]
