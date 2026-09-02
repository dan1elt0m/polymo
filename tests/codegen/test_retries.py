from __future__ import annotations

from itertools import count

import pytest

from polymo.codegen import generate_core
from polymo.config import BackoffConfig, ErrorHandlerConfig
from tests.codegen.helpers import make_config, run_generated


def test_retries_5xx_then_succeeds(http_server):
    attempts = count()
    http_server.routes["/posts"] = lambda q, h, b: (
        (500, {"err": "boom"}, {}) if next(attempts) < 2 else (200, [{"id": 1}], {})
    )
    config = make_config(
        base_url=http_server.url,
        error_handler=ErrorHandlerConfig(
            max_retries=3,
            backoff=BackoffConfig(initial_delay_seconds=0.0, max_delay_seconds=0.0),
        ),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}]
    assert len(http_server.log) == 3


def test_status_not_retryable_raises(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (404, {"err": "nope"}, {})
    config = make_config(base_url=http_server.url)
    module = run_generated(config)
    try:
        list(module.fetch_records())
        raise AssertionError("expected HTTPError")
    except Exception as exc:  # requests.HTTPError, but namespace-local
        assert "404" in str(exc)


# --- specialized retry/backoff code (no literals interpolated into
# conditions -- see tests/codegen/test_lean_output.py) --------------------


def test_retry_on_timeout_false_does_not_catch_timeout():
    """`retry_on_timeout=False` should mean Timeout isn't even caught."""
    config = make_config(
        base_url="https://x",
        error_handler=ErrorHandlerConfig(retry_on_timeout=False, max_retries=3),
    )
    module = run_generated(config)
    calls = {"n": 0}

    class FakeSession:
        def get(self, url, params=None, timeout=None):
            calls["n"] += 1
            raise module.requests.exceptions.Timeout("boom")

    with pytest.raises(module.requests.exceptions.Timeout):
        module._request(FakeSession(), "https://x/posts", {})
    assert calls["n"] == 1


def test_retry_on_timeout_true_retries_until_max_retries():
    config = make_config(
        base_url="https://x",
        error_handler=ErrorHandlerConfig(
            retry_on_timeout=True,
            max_retries=3,
            backoff=BackoffConfig(initial_delay_seconds=0.0, max_delay_seconds=0.0),
        ),
    )
    module = run_generated(config)
    calls = {"n": 0}

    class FakeSession:
        def get(self, url, params=None, timeout=None):
            calls["n"] += 1
            raise module.requests.exceptions.Timeout("boom")

    with pytest.raises(module.requests.exceptions.Timeout):
        module._request(FakeSession(), "https://x/posts", {})
    assert calls["n"] == 4  # initial attempt + 3 retries


def test_retry_on_connection_errors_false_does_not_catch_it():
    config = make_config(
        base_url="https://x",
        error_handler=ErrorHandlerConfig(
            retry_on_connection_errors=False, max_retries=3
        ),
    )
    module = run_generated(config)
    calls = {"n": 0}

    class FakeSession:
        def get(self, url, params=None, timeout=None):
            calls["n"] += 1
            raise module.requests.exceptions.ConnectionError("boom")

    with pytest.raises(module.requests.exceptions.ConnectionError):
        module._request(FakeSession(), "https://x/posts", {})
    assert calls["n"] == 1


def test_max_retries_zero_produces_minimal_request(http_server):
    """No retries at all: plain `session.get` + `raise_for_status`, no loop."""
    config = make_config(
        base_url=http_server.url,
        error_handler=ErrorHandlerConfig(max_retries=0),
    )
    script = generate_core(config)
    assert "import time" not in script
    assert "def _should_retry" not in script
    assert "INITIAL_DELAY" not in script
    assert "for attempt in range" not in script
    assert 'raise RuntimeError("unreachable")' not in script

    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}], {})
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}]

    http_server.routes["/posts"] = lambda q, h, b: (500, {"err": "boom"}, {})
    module = run_generated(config)
    calls_before = len(http_server.log)
    with pytest.raises(Exception) as exc_info:
        list(module.fetch_records())
    assert "500" in str(exc_info.value)
    assert len(http_server.log) == calls_before + 1  # no retry loop to repeat the call
