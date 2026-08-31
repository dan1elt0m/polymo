"""Public entrypoints for the polymo REST data source."""

from __future__ import annotations

from .codegen import CodegenError, generate
from .config import (
    RestSourceConfig,
    config_to_dict,
    parse_config,
)

__all__ = [
    "generate",
    "CodegenError",
    "RestSourceConfig",
    "config_to_dict",
    "parse_config",
]
