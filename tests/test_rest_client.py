from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, List

import httpx
import pytest

from polymo.config import (
    AuthConfig,
    BackoffConfig,
    ErrorHandlerConfig,
    IncrementalConfig,
    PaginationConfig,
    RecordSelectorConfig,
    StreamConfig,
)
from polymo.rest_client import RestClient
import polymo.rest_client as rest_client_module

Handler = Callable[[httpx.Request], httpx.Response]


@pytest.fixture(autouse=True)
def disable_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rest_client_module.time, "sleep", lambda _: None)


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


def test_fetch_records_offset_pagination(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params.get("offset", "0"))
        limit = request.url.params.get("limit")
        assert limit == "1"

        if offset == 0:
            return httpx.Response(200, json=[{"id": 1}])
        if offset == 1:
            return httpx.Response(200, json=[{"id": 2}])
        if offset == 2:
            return httpx.Response(200, json=[])
        pytest.fail(f"Unexpected offset: {offset}")

    calls = install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/items",
        pagination=PaginationConfig(
            type="offset",
            page_size=1,
            limit_param="limit",
            offset_param="offset",
        ),
    )

    client = RestClient(base_url="https://example.com", auth=AuthConfig())
    pages = list(client.fetch_records(stream))

    assert pages == [[{"id": 1}], [{"id": 2}], []]
    assert [req.url.params.get("offset") for req in calls] == ["0", "1", "2"]


def test_fetch_records_page_pagination(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        page = int(request.url.params.get("page", "0"))
        assert request.url.params.get("per_page") == "2"

        if page == 1:
            return httpx.Response(200, json=[{"id": 10}, {"id": 11}])
        if page == 2:
            return httpx.Response(200, json=[{"id": 12}])
        if page == 3:
            return httpx.Response(200, json=[])
        pytest.fail(f"Unexpected page: {page}")

    calls = install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/paged",
        pagination=PaginationConfig(
            type="page",
            page_size=2,
            limit_param="per_page",
            page_param="page",
        ),
    )

    client = RestClient(base_url="https://example.com", auth=AuthConfig())
    pages = list(client.fetch_records(stream))

    assert pages == [[{"id": 10}, {"id": 11}], [{"id": 12}], []]
    assert [req.url.params.get("page") for req in calls] == ["1", "2", "3"]


def test_fetch_records_cursor_pagination(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        if cursor is None:
            payload = {"data": [{"id": 1}], "next_cursor": "token-1"}
            return httpx.Response(200, json=payload)
        if cursor == "token-1":
            payload = {"data": [{"id": 2}], "next_cursor": None}
            return httpx.Response(200, json=payload)
        pytest.fail(f"Unexpected cursor: {cursor}")

    calls = install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/cursor",
        pagination=PaginationConfig(
            type="cursor",
            cursor_param="cursor",
            cursor_path=("next_cursor",),
        ),
    )

    client = RestClient(base_url="https://example.com", auth=AuthConfig())
    pages = list(client.fetch_records(stream))

    assert pages == [[{"id": 1}], [{"id": 2}]]
    assert [req.url.params.get("cursor") for req in calls] == [None, "token-1"]


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


def test_incremental_uses_state_value_for_query(
    install_transport: Callable[[Handler], List[httpx.Request]],
    tmp_path: Path,
) -> None:
    rest_client_module._MEMORY_STATE.clear()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_path = state_dir / "cursor.json"
    state_payload = {
        "streams": {
            "sample@https://example.com": {
                "cursor_value": "2024-01-01T00:00:00Z",
            }
        }
    }
    state_path.write_text(json.dumps(state_payload))

    observed_params: List[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed_params.append(request.url.params.get("since"))
        return httpx.Response(200, json=[{"id": 1, "updated_at": "2024-01-02T00:00:00Z"}])

    install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/records",
        incremental=IncrementalConfig(
            mode="updated_at",
            cursor_param="since",
            cursor_field="updated_at",
        ),
    )

    client = RestClient(
        base_url="https://example.com",
        auth=AuthConfig(),
        options={"incremental_state_path": str(state_path)},
    )

    list(client.fetch_records(stream))

    assert observed_params == ["2024-01-01T00:00:00Z"]


def test_incremental_persists_latest_value(
    install_transport: Callable[[Handler], List[httpx.Request]],
    tmp_path: Path,
) -> None:
    rest_client_module._MEMORY_STATE.clear()
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    state_path = state_dir / "cursor.json"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = [
            {"id": 1, "updated_at": "2024-01-01T08:00:00Z"},
            {"id": 2, "updated_at": "2024-01-03T12:30:00Z"},
        ]
        return httpx.Response(200, json=payload)

    install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/records",
        incremental=IncrementalConfig(
            mode="updated_at",
            cursor_param="since",
            cursor_field="updated_at",
        ),
    )

    client = RestClient(
        base_url="https://example.com",
        auth=AuthConfig(),
        options={"incremental_state_path": str(state_path)},
    )

    list(client.fetch_records(stream))

    saved = json.loads(state_path.read_text())
    entry = saved["streams"]["sample@https://example.com"]
    assert entry["cursor_value"] == "2024-01-03T12:30:00Z"
    assert entry["cursor_field"] == "updated_at"
    assert entry["cursor_param"] == "since"


def test_incremental_start_value_option(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    rest_client_module._MEMORY_STATE.clear()
    observed: List[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.params.get("since"))
        return httpx.Response(200, json=[])

    install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/records",
        incremental=IncrementalConfig(
            mode="updated_at",
            cursor_param="since",
            cursor_field="updated_at",
        ),
    )

    client = RestClient(
        base_url="https://example.com",
        auth=AuthConfig(),
        options={"incremental_start_value": "baseline"},
    )

    list(client.fetch_records(stream))

    assert observed == ["baseline"]


def test_incremental_memory_roundtrip(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    rest_client_module._MEMORY_STATE.clear()

    observed: List[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.params.get("since"))
        return httpx.Response(200, json=[{"id": 1, "updated_at": "2024-02-01T06:00:00Z"}])

    install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/records",
        incremental=IncrementalConfig(
            mode="updated_at",
            cursor_param="since",
            cursor_field="updated_at",
        ),
    )

    first_client = RestClient(
        base_url="https://example.com",
        auth=AuthConfig(),
        options={"incremental_start_value": "baseline"},
    )

    list(first_client.fetch_records(stream))

    second_client = RestClient(base_url="https://example.com", auth=AuthConfig())

    list(second_client.fetch_records(stream))

    assert observed == ["baseline", "2024-02-01T06:00:00Z"]


def test_incremental_memory_can_be_disabled(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    rest_client_module._MEMORY_STATE.clear()

    observed: List[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.params.get("since"))
        return httpx.Response(200, json=[{"id": 1, "updated_at": "2024-02-01T06:00:00Z"}])

    install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/records",
        incremental=IncrementalConfig(
            mode="updated_at",
            cursor_param="since",
            cursor_field="updated_at",
        ),
    )

    first_client = RestClient(
        base_url="https://example.com",
        auth=AuthConfig(),
        options={
            "incremental_start_value": "baseline",
            "incremental_memory_state": "false",
        },
    )

    list(first_client.fetch_records(stream))

    assert rest_client_module._MEMORY_STATE == {}

    second_client = RestClient(base_url="https://example.com", auth=AuthConfig())

    list(second_client.fetch_records(stream))

    assert observed == ["baseline", None]


def test_error_handler_retries_server_error(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"detail": "temporary"})
        return httpx.Response(200, json=[{"ok": True}])

    install_transport(handler)

    stream = StreamConfig(name="sample", path="/data")
    client = RestClient(base_url="https://example.com", auth=AuthConfig())

    pages = list(client.fetch_records(stream))

    assert attempts == 2
    assert pages == [[{"ok": True}]]


def test_error_handler_can_retry_custom_status(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return httpx.Response(404, json={"detail": "not ready"})
        return httpx.Response(200, json=[{"ok": True}])

    install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/data",
        error_handler=ErrorHandlerConfig(
            retry_statuses=("404",),
            max_retries=3,
            backoff=BackoffConfig(initial_delay_seconds=0.0, max_delay_seconds=0.0, multiplier=1.0),
        ),
    )

    client = RestClient(base_url="https://example.com", auth=AuthConfig())

    pages = list(client.fetch_records(stream))

    assert attempts == 2
    assert pages == [[{"ok": True}]]


def test_error_handler_exhausts_retries(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        return httpx.Response(503, json={"message": "unavailable"})

    install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/data",
        error_handler=ErrorHandlerConfig(max_retries=2),
    )

    client = RestClient(base_url="https://example.com", auth=AuthConfig())

    with pytest.raises(RuntimeError, match="503"):
        list(client.fetch_records(stream))

    assert attempts == 3


def test_incremental_remote_state_path(
    install_transport: Callable[[Handler], List[httpx.Request]]
) -> None:
    pytest.importorskip("fsspec")
    import fsspec

    rest_client_module._MEMORY_STATE.clear()

    fs = fsspec.filesystem("memory")
    if hasattr(fs, "store"):
        fs.store.clear()

    remote_path = "memory://polymo/state/cursor.json"

    observed: List[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(request.url.params.get("since"))
        return httpx.Response(200, json=[{"id": 1, "updated_at": "2024-05-04T00:00:00Z"}])

    install_transport(handler)

    stream = StreamConfig(
        name="sample",
        path="/records",
        incremental=IncrementalConfig(
            mode="updated_at",
            cursor_param="since",
            cursor_field="updated_at",
        ),
    )

    first_client = RestClient(
        base_url="https://example.com",
        auth=AuthConfig(),
        options={
            "incremental_state_path": remote_path,
            "incremental_start_value": "baseline",
        },
    )

    list(first_client.fetch_records(stream))

    with fsspec.open(remote_path, "r") as handle:
        payload = json.load(handle)

    entry = payload["streams"]["sample@https://example.com"]
    assert entry["cursor_value"] == "2024-05-04T00:00:00Z"

    second_client = RestClient(
        base_url="https://example.com",
        auth=AuthConfig(),
        options={"incremental_state_path": remote_path},
    )

    list(second_client.fetch_records(stream))

    assert observed == ["baseline", "2024-05-04T00:00:00Z"]
