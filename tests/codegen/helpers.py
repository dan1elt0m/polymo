from __future__ import annotations

import ast
import re
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

from polymo.codegen import generate_core
from polymo.config import AuthConfig, RestSourceConfig, StreamConfig


def make_config(
    *,
    base_url: str,
    auth: AuthConfig | None = None,
    options: dict[str, Any] | None = None,
    **stream_kwargs: Any,
) -> RestSourceConfig:
    stream_kwargs.setdefault("name", "posts")
    stream_kwargs.setdefault("path", "/posts")
    return RestSourceConfig(
        version="0.1",
        base_url=base_url,
        auth=auth or AuthConfig(),
        stream=StreamConfig(**stream_kwargs),
        options=options or {},
    )


def assert_hygiene(code: str) -> None:
    ast.parse(code)
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--no-cache",
            "--stdin-filename",
            "gen.py",
            "-",
        ],
        input=code.encode(),
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout.decode() + result.stderr.decode()


def run_generated(
    config: RestSourceConfig, override_globals: dict[str, Any] | None = None
) -> SimpleNamespace:
    code = generate_core(config)
    assert_hygiene(code)
    overrides = override_globals or {}
    # Some placeholder constants (API_TOKEN, CLIENT_SECRET, OPT_*) are baked
    # into a module-level literal (e.g. `HEADERS: dict = {...OPT_X...}`)
    # that's evaluated once, at exec time — a plain `namespace.update(...)`
    # *after* exec can't retroactively change what that literal already
    # captured. Substituting the constant's default `"REPLACE_ME"` value in
    # the source text before exec mimics what a user actually does (editing
    # the file), so overrides reach eagerly-baked literals too. Constants
    # only ever read lazily inside a function body (like the bearer/oauth2
    # ones) don't need this, but it's harmless for them either way.
    for name, value in overrides.items():
        # `(?:: \S+)?` skips the optional `: str` type annotation the
        # generator now emits on these constants.
        pattern = re.compile(
            rf'^{re.escape(name)}(?:: \S+)? = "REPLACE_ME"$', re.MULTILINE
        )
        code = pattern.sub(f"{name} = {value!r}", code, count=1)
    namespace: dict[str, Any] = {}
    exec(compile(code, "<generated>", "exec"), namespace)  # noqa: S102
    namespace.update(overrides)
    return SimpleNamespace(**namespace)
