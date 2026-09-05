"""Shared plumbing for the live public-API suite.

Every test here follows the same shape: build a `RestSourceConfig` the way
the UI would, `generate()` the standalone script, exec it unmodified
(the `spark_session` fixture stubs the Databricks-only `pyspark.pipelines`
module), and read the registered Python Data Source back through
`spark.read.format(...)` / `spark.readStream.format(...)` exactly as a
Lakeflow pipeline would.
"""

from __future__ import annotations

import os
import re
from typing import Any

from polymo.codegen import generate
from polymo.config import (
    AuthConfig,
    BackoffConfig,
    ErrorHandlerConfig,
    RestSourceConfig,
    StreamConfig,
)
from tests.codegen.helpers import assert_hygiene

USER_AGENT = "polymo-live-tests (+https://github.com/dan1elt0m/polymo)"

# Public APIs occasionally answer 5xx under load; two quick retries keep the
# suite honest without letting a genuinely-down API stall a run for minutes.
FAST_RETRIES = ErrorHandlerConfig(
    max_retries=2,
    backoff=BackoffConfig(initial_delay_seconds=0.5, max_delay_seconds=2.0),
)


def live_config(
    *,
    base_url: str,
    name: str,
    path: str,
    auth: AuthConfig | None = None,
    options: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    error_handler: ErrorHandlerConfig = FAST_RETRIES,
    **stream_kwargs: Any,
) -> RestSourceConfig:
    return RestSourceConfig(
        version="0.1",
        base_url=base_url,
        auth=auth or AuthConfig(),
        stream=StreamConfig(
            name=name,
            path=path,
            headers={"User-Agent": USER_AGENT, **(headers or {})},
            error_handler=error_handler,
            **stream_kwargs,
        ),
        options=options or {},
    )


def install_placeholders(script: str, **values: str) -> str:
    """Fill `NAME: str = "REPLACE_ME"` slots the way a user edits the export.

    Secrets never land in generated code: bearer tokens, API keys, OAuth2
    client secrets and unresolved `{{ options.* }}` references all come out
    as `"REPLACE_ME"` constants. Substituting them in the source text (not
    the exec'd namespace) also reaches literals that captured the constant
    at import time, e.g. an f-string inside `HEADERS`.
    """
    for name, value in values.items():
        pattern = re.compile(rf'^{re.escape(name)}: str = "REPLACE_ME"$', re.MULTILINE)
        script, count = pattern.subn(f"{name}: str = {value!r}", script, count=1)
        assert count == 1, f"{name} placeholder not found in generated script"
    return script


def exec_script(script: str) -> dict[str, Any]:
    assert_hygiene(script)
    namespace: dict[str, Any] = {}
    exec(compile(script, "<generated>", "exec"), namespace)  # noqa: S102
    return namespace


def registered_format(script: str) -> str:
    """The `spark.read(Stream).format("<name>")` the script's dp table uses."""
    match = re.search(r'spark\.read(?:Stream)?\.format\("([^"]+)"\)', script)
    assert match, "generated script has no spark.read(...).format(...) call"
    return match.group(1)


def read_batch(spark, config: RestSourceConfig, **placeholders: str):
    """Generate, exec and `spark.read` the batch table for `config`."""
    script = install_placeholders(generate(config), **placeholders)
    exec_script(script)
    return spark.read.format(registered_format(script)).load()


def github_auth() -> tuple[AuthConfig, dict[str, str]]:
    """Bearer auth when `GITHUB_TOKEN` is set (CI), anonymous otherwise.

    Anonymous GitHub API access is limited to 60 requests/hour per IP; the
    suite needs fewer than ten, but a token (GitHub Actions provides one)
    keeps repeated local runs from tripping the limit.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return AuthConfig(type="bearer"), {"API_TOKEN": token}
    return AuthConfig(), {}
