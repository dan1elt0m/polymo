"""Public entrypoints for the polymo REST data source."""

from __future__ import annotations

from .config import (
    RestSourceConfig,
    config_to_dict,
    dump_config,
    load_config,
    parse_config,
)
from .datasource import ApiReader
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
    "ApiReader",
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


def _alias_datasource(name: str) -> type[ApiReader]:
    alias_name = name

    class AliasRestDataSource(ApiReader):
        @classmethod
        def name(cls) -> str:  # type: ignore[override]
            return alias_name

    AliasRestDataSource.__name__ = f"RestDataSource_{name.replace('.', '_')}"
    AliasRestDataSource.__qualname__ = AliasRestDataSource.__name__
    AliasRestDataSource.__module__ = ApiReader.__module__
    return AliasRestDataSource
