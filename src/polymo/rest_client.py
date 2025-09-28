"""Minimal REST client capable of streaming pages for the connector."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional

import httpx
from jinja2 import Environment, StrictUndefined, TemplateError

from pyspark.sql.types import (
    ArrayType,
    BooleanType,
    ByteType,
    DateType,
    DecimalType,
    DoubleType,
    FloatType,
    IntegerType,
    LongType,
    MapType,
    ShortType,
    StringType,
    StructType,
    TimestampType,
)

from .config import (
    AuthConfig,
    PaginationConfig,
    RecordSelectorConfig,
    StreamConfig,
    parse_schema_struct,
)


USER_AGENT = "polymo-rest-source/0.1"

_FILTER_ENV = Environment(undefined=StrictUndefined, autoescape=False)
_FILTER_CACHE: Dict[str, Any] = {}
_TEMPLATE_ENV = Environment(undefined=StrictUndefined, autoescape=False)


@dataclass
class RestPage:
    """Representation of a single page returned by the REST API."""

    records: List[Mapping[str, Any]]
    payload: Any
    url: str
    status_code: int
    headers: Mapping[str, str]


@dataclass
class RestClient:
    """Thin HTTP client tailored for REST-to-DataFrame ingestion."""

    base_url: str
    auth: AuthConfig
    timeout: float = 30.0
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        headers = {"User-Agent": USER_AGENT}
        if self.auth.type == "bearer" and self.auth.token:
            headers["Authorization"] = f"Bearer {self.auth.token}"

        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    def fetch_records(self, stream: StreamConfig) -> Iterator[List[Mapping[str, Any]]]:
        """Yield pages of JSON records for the provided stream definition."""

        for page in self.fetch_pages(stream):
            yield page.records

    def fetch_pages(self, stream: StreamConfig) -> Iterator[RestPage]:
        """Yield pages with rich metadata for the provided stream definition."""

        template_context: Dict[str, Any] = {
            "options": dict(self.options or {}),
            "params": dict(stream.params or {}),
            "headers": dict(stream.headers or {}),
            "raw_params": dict(stream.params or {}),
        }

        rendered_params = {
            key: _render_template(value, template_context)
            for key, value in stream.params.items()
        } if stream.params else {}

        template_context["params"] = rendered_params

        formatter = _PathFormatter(rendered_params)
        rendered_path = _render_template(stream.path, template_context)
        path = formatter.render(rendered_path)

        query_params = {
            key: _render_template(value, template_context)
            for key, value in formatter.remaining_params().items()
        }
        pagination = stream.pagination

        request_headers: Dict[str, str] = {}
        if stream.headers:
            for key, value in stream.headers.items():
                request_headers[key] = _render_template(value, template_context)

        declared_schema = _resolve_schema(stream)

        yield from self._iterate_pages(
            initial_path=path,
            query_params=query_params,
            pagination=pagination,
            request_headers=request_headers if request_headers else None,
            stream=stream,
            declared_schema=declared_schema,
        )

    def _iterate_pages(
        self,
        *,
        initial_path: str,
        query_params: Dict[str, Any],
        pagination: PaginationConfig,
        request_headers: Optional[Dict[str, str]],
        stream: StreamConfig,
        declared_schema: Optional[StructType],
    ) -> Iterator[RestPage]:
        next_url: Optional[str] = initial_path

        while next_url:
            response = self._client.get(
                next_url,
                params=query_params if next_url == initial_path else None,
                headers=request_headers,
            )
            response.raise_for_status()
            payload = response.json()

            records = _extract_records(payload, stream.record_selector, declared_schema)
            if not isinstance(records, list):
                raise ValueError("Expected API response to be a list of records")

            yield RestPage(
                records=records,
                payload=payload,
                url=str(response.url),
                status_code=response.status_code,
                headers=dict(response.headers),
            )

            next_url = _next_page(response, pagination)

    def __enter__(self) -> "RestClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _render_template(value: Any, context: Mapping[str, Any]) -> Any:
    if not isinstance(value, str):
        return value
    if "{{" not in value and "{%" not in value:
        return value
    try:
        template = _TEMPLATE_ENV.from_string(value)
        return template.render(**context)
    except TemplateError as exc:
        raise ValueError(f"Error rendering template: {exc}") from exc


def _extract_records(
    payload: Any,
    selector: RecordSelectorConfig,
    declared_schema: Optional[StructType],
) -> List[Mapping[str, Any]]:
    """Apply record selector settings to a response payload."""

    records: Any
    if selector.field_path:
        records = _select_field_path(payload, selector.field_path)
    else:
        records = _normalise_payload(payload)

    if not isinstance(records, list):
        records = [records]

    if selector.record_filter:
        records = _filter_records(records, selector.record_filter)

    if selector.cast_to_schema_types and declared_schema is not None:
        records = [_cast_record(record, declared_schema) for record in records]

    # Ensure we always return list of mappings
    final: List[Mapping[str, Any]] = []
    for record in records:
        if isinstance(record, Mapping):
            final.append(dict(record))
        else:
            final.append({"record": record})
    return final


def _normalise_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # Accept top-level "data" or "items" wrappers.
        for key in ("data", "items", "results"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    return payload


def _select_field_path(payload: Any, field_path: Iterable[str]) -> List[Any]:
    """Traverse payload using Airbyte-style field path semantics."""

    current: List[Any] = [payload]
    # Always start with a * to handle top-level lists
    if field_path[0] != "*":
        field_path = ("*",) + tuple(field_path)

    for segment in field_path:
        next_level: List[Any] = []
        if segment == "*":
            for item in current:
                if isinstance(item, list):
                    next_level.extend(item)
                elif isinstance(item, Mapping):
                    next_level.extend(item.values())
        else:
            for item in current:
                if isinstance(item, Mapping) and segment in item:
                    next_level.append(item[segment])
        current = next_level

    flattened: List[Any] = []
    for item in current:
        if isinstance(item, list):
            flattened.extend(item)
        else:
            flattened.append(item)
    return flattened


def _filter_records(records: List[Any], expression: str) -> List[Any]:
    """Filter records using a cached Jinja expression."""

    expr = expression.strip()
    if not expr:
        return records
    if expr not in _FILTER_CACHE:
        stripped = expr
        if expr.startswith("{{") and expr.endswith("}}"): 
            stripped = expr[2:-2].strip()
        try:
            _FILTER_CACHE[expr] = _FILTER_ENV.compile_expression(stripped)
        except TemplateError as exc:
            raise ValueError(f"Invalid record filter expression: {exc}") from exc

    compiled = _FILTER_CACHE[expr]
    filtered: List[Any] = []
    for record in records:
        context = {"record": record}
        try:
            result = compiled(**context)
        except TemplateError as exc:
            raise ValueError(f"Error evaluating record filter: {exc}") from exc
        include = _coerce_to_bool(result)
        if include:
            filtered.append(record)
    return filtered


def _coerce_to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y", "on"}
    return bool(value)


def _resolve_schema(stream: StreamConfig) -> Optional[StructType]:
    if not stream.record_selector.cast_to_schema_types:
        return None
    schema_text = stream.schema
    if not schema_text:
        return None
    try:
        return parse_schema_struct(schema_text)
    except Exception:
        return None
    return None


def _cast_record(record: Mapping[str, Any], schema: StructType) -> Mapping[str, Any]:
    if not isinstance(record, Mapping):
        return record
    casted: Dict[str, Any] = dict(record)
    for field in schema.fields:
        if field.name in casted:
            casted[field.name] = _cast_value(casted[field.name], field.dataType)
    return casted


def _cast_value(value: Any, datatype: Any) -> Any:
    if value is None:
        return None
    if isinstance(datatype, (StringType,)):
        return str(value)
    if isinstance(datatype, BooleanType):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y", "on"}:
                return True
            if lowered in {"false", "0", "no", "n", "off"}:
                return False
        return bool(value)
    if isinstance(datatype, (ByteType, ShortType, IntegerType, LongType)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return value
    if isinstance(datatype, (FloatType, DoubleType)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return value
    if isinstance(datatype, DecimalType):
        try:
            return Decimal(str(value))
        except (ArithmeticError, ValueError):
            return value
    if isinstance(datatype, TimestampType):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError:
                return value
        return value
    if isinstance(datatype, DateType):
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value.replace("Z", "")).date()
            except ValueError:
                return value
        return value
    if isinstance(datatype, ArrayType):
        if isinstance(value, list):
            return [_cast_value(item, datatype.elementType) for item in value]
        return value
    if isinstance(datatype, MapType):
        if isinstance(value, Mapping):
            return {key: _cast_value(val, datatype.valueType) for key, val in value.items()}
        return value
    if isinstance(datatype, StructType):
        if isinstance(value, Mapping):
            nested = dict(value)
            for field in datatype.fields:
                if field.name in nested:
                    nested[field.name] = _cast_value(nested[field.name], field.dataType)
            return nested
        return value
    return value


def _next_page(response: httpx.Response, pagination: PaginationConfig) -> Optional[str]:
    if pagination.type != "link_header":
        return None

    link_header = response.headers.get("Link")
    if not link_header:
        return None

    for link in link_header.split(","):
        parts = link.split(";")
        if len(parts) < 2:
            continue
        url_part = parts[0].strip()
        rel_part = ",".join(parts[1:]).strip()
        if 'rel="next"' in rel_part:
            return url_part.strip("<>")
    return None


class _PathFormatter:
    """Shallow helper to substitute params into the path while retaining query params."""

    def __init__(self, params: Mapping[str, Any]):
        self._params = dict(params)
        self._consumed: Dict[str, Any] = {}

    def render(self, path: str) -> str:
        substituted = path
        for key, value in list(self._params.items()):
            placeholder = "{" + key + "}"
            if placeholder in substituted:
                substituted = substituted.replace(placeholder, str(value))
                self._consumed[key] = self._params.pop(key)
        return substituted

    def remaining_params(self) -> Dict[str, Any]:
        return dict(self._params)
