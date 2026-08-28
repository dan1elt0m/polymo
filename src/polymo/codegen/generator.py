"""Render standalone Lakeflow Declarative Pipelines scripts from a config."""

from __future__ import annotations

import re
from typing import Any, Dict

from jinja2 import Environment, PackageLoader, StrictUndefined

from ..config import RestSourceConfig


class CodegenError(Exception):
    """Raised when a config cannot be expressed as a generated script."""


_ENV = Environment(
    loader=PackageLoader("polymo.codegen", "templates"),
    undefined=StrictUndefined,
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
)


def _identifier(name: str) -> str:
    cleaned = re.sub(r"\W", "_", name)
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return cleaned


def _context(config: RestSourceConfig) -> Dict[str, Any]:
    stream = config.stream
    return {
        "base_url": config.base_url.rstrip("/"),
        "path": stream.path,
        "params_repr": repr(dict(stream.params or {})),
        "headers_repr": repr(dict(stream.headers or {})),
        "stream_name": stream.name,
        "func_name": _identifier(stream.name),
    }


def generate_core(config: RestSourceConfig) -> str:
    return _ENV.get_template("core.py.jinja").render(**_context(config))


def generate(config: RestSourceConfig) -> str:
    core = generate_core(config)
    dp_wiring = _ENV.get_template("dp.py.jinja").render(**_context(config))
    return core + "\n\n" + dp_wiring
