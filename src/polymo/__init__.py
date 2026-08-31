"""Public entrypoints for the polymo REST data source."""

from __future__ import annotations

from .codegen import CodegenError, generate
from .config import (
    RestSourceConfig,
    config_to_dict,
    dump_config,
    load_config,
    parse_config,
)
from .pydantic_config import (
    PolymoConfig,
    AuthModel,
    BackoffModel,
    ErrorHandlerModel,
    IncrementalModel,
    PaginationModel,
    PartitionModel,
    RecordSelectorModel,
    SourceModel,
    StreamModel,
)

__all__ = [
    "CodegenError",
    "generate",
    "RestSourceConfig",
    "config_to_dict",
    "dump_config",
    "load_config",
    "parse_config",
    "PolymoConfig",
    "SourceModel",
    "StreamModel",
    "PaginationModel",
    "IncrementalModel",
    "RecordSelectorModel",
    "ErrorHandlerModel",
    "BackoffModel",
    "PartitionModel",
    "AuthModel",
]
