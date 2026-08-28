from __future__ import annotations

from itertools import count

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
