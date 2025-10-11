#!/usr/bin/env python
# ruff: noqa

"""Generate Markdown reference for the Polymo Pydantic configuration models."""

from __future__ import annotations

from unittest.mock import MagicMock

from pathlib import Path
import sys
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
    Union,
    get_args,
    get_origin,
)

from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
for path in (SRC_PATH, PROJECT_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

# Mock the pyspark module so that it doesn't throw an error during tests
sys.modules["pyspark.sql"] = MagicMock()
sys.modules["pyspark.sql.types"] = MagicMock()
sys.modules["pyspark.sql.datasource"] = MagicMock()
sys.modules["pyarrow"] = MagicMock()
sys.modules["httpx"] = MagicMock()
sys.modules["jinja2"] = MagicMock()

from polymo.pydantic_config import (
    AuthModel,
    BackoffModel,
    ErrorHandlerModel,
    IncrementalModel,
    PaginationModel,
    PartitionModel,
    PolymoConfig,
    RecordSelectorModel,
    StreamModel,
)

OUTPUT_PATH = Path(__file__).with_name("polymo_config_reference.md")
HEADER = """# Polymo Configuration Reference

> This document is generated automatically from the Pydantic models in `polymo.pydantic_config`.

"""

MODEL_ORDER: List[Tuple[str, Any]] = [
    ("PolymoConfig", PolymoConfig),
    ("AuthModel", AuthModel),
    ("PaginationModel", PaginationModel),
    ("IncrementalModel", IncrementalModel),
    ("RecordSelectorModel", RecordSelectorModel),
    ("PartitionModel", PartitionModel),
    ("BackoffModel", BackoffModel),
    ("ErrorHandlerModel", ErrorHandlerModel),
    ("StreamModel", StreamModel),
]

MODEL_NAMES = {model: name for name, model in MODEL_ORDER}


def _format_type(annotation: Any) -> str:
    origin = get_origin(annotation)
    if origin is None:
        if hasattr(annotation, "__name"):
            return str(annotation.__name__)
        if hasattr(annotation, "__name__"):
            return annotation.__name__
        return str(annotation).replace("typing.", "")

    args = get_args(annotation)
    if origin is Union:
        non_optional = [arg for arg in args if arg is not type(None)]
        inner = ", ".join(_format_type(arg) for arg in non_optional) or "Any"
        if len(non_optional) < len(args):
            return f"Optional[{inner}]"
        return f"Union[{inner}]"
    if origin is list or origin is List:
        inner = _format_type(args[0]) if args else "Any"
        return f"List[{inner}]"
    if origin is dict or origin is Dict:
        key = _format_type(args[0]) if args else "Any"
        value = _format_type(args[1]) if len(args) > 1 else "Any"
        return f"Dict[{key}, {value}]"
    if origin is Sequence:
        inner = _format_type(args[0]) if args else "Any"
        return f"Sequence[{inner}]"
    if origin is Tuple:
        inner = ", ".join(_format_type(arg) for arg in args)
        return f"Tuple[{inner}]"
    formatted_args = ", ".join(_format_type(arg) for arg in args)
    return f"{_format_type(origin)}[{formatted_args}]"


def _format_default(field: FieldInfo) -> str:
    if field.default is not PydanticUndefined:
        value = field.default
        if callable(value):
            return "`<callable>`"
        if isinstance(value, str):
            return f"`{value}`"
        return f"`{value!r}`"
    if field.default_factory is not None:
        return "`<factory>`"
    return "—"


def _maybe_add_model_link(annotation: Any) -> Optional[str]:
    annotations = []
    origin = get_origin(annotation)
    if origin:
        annotations.extend(get_args(annotation))
    else:
        annotations.append(annotation)

    for ann in annotations:
        if ann in MODEL_NAMES:
            name = MODEL_NAMES[ann]
            return f" See [{name}](#{name.lower()})."
    return None


def render_model(name: str, model: Any) -> str:
    lines = [f"## {name}\n"]
    description = getattr(model, "__doc__", "") or ""
    if description.strip():
        lines.append(f"{description.strip()}\n")

    lines.append("| Field | Type | Default | Description |")
    lines.append("| --- | --- | --- | --- |")

    for field_name, field in model.model_fields.items():
        field_type = _format_type(field.annotation)
        default_val = _format_default(field)
        description = field.description or ""
        link_extra = _maybe_add_model_link(field.annotation)
        if link_extra:
            description += link_extra
        description = description.replace("\n", " ")
        lines.append(
            f"| `{field_name}` | `{field_type}` | {default_val} | {description or '—'} |"
        )

    lines.append("")
    return "\n".join(lines)


def main() -> None:
    sections = [HEADER]
    for name, model in MODEL_ORDER:
        sections.append(render_model(name, model))
    OUTPUT_PATH.write_text("\n".join(sections).rstrip() + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
