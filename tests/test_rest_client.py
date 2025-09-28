from __future__ import annotations

from typing import Any, Callable, List

import httpx
import pytest

from polymo.config import AuthConfig, PaginationConfig, RecordSelectorConfig, StreamConfig
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


def test_record_selector_field_path(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {"response": {"docs": [{"id": 10}, {"id": 11}]}}
        return httpx.Response(200, json=payload)

    install_transport(handler)

    selector = RecordSelectorConfig(field_path=["response", "docs"])
    stream = StreamConfig(name="sample", path="/data", record_selector=selector)
    client = RestClient(base_url="https://example.com", auth=AuthConfig())

    pages = list(client.fetch_records(stream))

    assert pages == [[{"id": 10}, {"id": 11}]]


def test_record_selector_wildcard_path(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = {"data": [{"record": {"id": 1}}, {"record": {"id": 2}}]}
        return httpx.Response(200, json=payload)

    install_transport(handler)

    selector = RecordSelectorConfig(field_path=["data", "*", "record"])
    stream = StreamConfig(name="sample", path="/data", record_selector=selector)
    client = RestClient(base_url="https://example.com", auth=AuthConfig())

    pages = list(client.fetch_records(stream))

    assert pages == [[{"id": 1}, {"id": 2}]]


def test_record_selector_filter(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = [
            {"id": 1, "status": "active"},
            {"id": 2, "status": "expired"},
            {"id": 3, "status": "active"},
        ]
        return httpx.Response(200, json=payload)

    install_transport(handler)

    selector = RecordSelectorConfig(record_filter="record.status == 'active'")
    stream = StreamConfig(name="sample", path="/data", record_selector=selector)
    client = RestClient(base_url="https://example.com", auth=AuthConfig())

    pages = list(client.fetch_records(stream))

    assert pages == [[{"id": 1, "status": "active"}, {"id": 3, "status": "active"}]]


def test_record_selector_casts_to_schema(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = [{"id": "123", "amount": "4.50"}]
        return httpx.Response(200, json=payload)

    install_transport(handler)

    selector = RecordSelectorConfig(cast_to_schema_types=True)
    stream = StreamConfig(
        name="sample",
        path="/data",
        record_selector=selector,
        schema="id INT, amount DOUBLE",
    )
    client = RestClient(base_url="https://example.com", auth=AuthConfig())

    pages = list(client.fetch_records(stream))

    assert pages == [[{"id": 123, "amount": 4.5}]]


def test_record_selector_invalid_filter_raises(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = [{"id": 1}]
        return httpx.Response(200, json=payload)

    install_transport(handler)

    selector = RecordSelectorConfig(record_filter="{{ record['")
    stream = StreamConfig(name="sample", path="/data", record_selector=selector)
    client = RestClient(base_url="https://example.com", auth=AuthConfig())

    with pytest.raises(ValueError, match="Invalid record filter"):
        list(client.fetch_records(stream))


def test_fetch_records_renders_option_templates(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get("api_key") == "secret123"
        return httpx.Response(200, json=[{"ok": True}])

    calls = install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/data",
        params={"api_key": "{{ options.api_key }}"},
        headers={"X-Custom": "Bearer {{ options.api_key }}"},
    )

    client = RestClient(
        base_url="https://example.com",
        auth=AuthConfig(),
        options={"api_key": "secret123"},
    )

    pages = list(client.fetch_records(stream))

    assert pages == [[{"ok": True}]]
    assert calls and calls[0].headers.get("X-Custom") == "Bearer secret123"


def test_fetch_records_missing_option_raises(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    install_transport(lambda request: httpx.Response(200, json=[]))

    stream = StreamConfig(
        name="sample",
        path="/data",
        params={"api_key": "{{ options.api_key }}"},
    )

    client = RestClient(base_url="https://example.com", auth=AuthConfig(), options={})

    with pytest.raises(ValueError, match="Error rendering template"):
        list(client.fetch_records(stream))
