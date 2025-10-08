"""Minimal REST client capable of streaming pages for the connector."""

from __future__ import annotations

import json
import posixpath
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional
from urllib.parse import urlparse

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
    ConfigError,
    ErrorHandlerConfig,
    PaginationConfig,
    RecordSelectorConfig,
    StreamConfig,
    parse_schema_struct,
)


USER_AGENT = "polymo-rest-source/0.1"

_FILTER_ENV = Environment(undefined=StrictUndefined, autoescape=False)
_FILTER_CACHE: Dict[str, Any] = {}
_TEMPLATE_ENV = Environment(undefined=StrictUndefined, autoescape=False)

_MEMORY_STATE: Dict[str, Dict[str, Any]] = {}


@dataclass
class RestPage:
    """Representation of a single page returned by the REST API."""

    records: List[Mapping[str, Any]]
    payload: Any
    url: str
    status_code: int
    headers: Mapping[str, str]


@dataclass(frozen=True)
class PaginationWindow:
    """Optional cursor to limit pagination to a specific slice."""

    page: Optional[int] = None
    offset: Optional[int] = None
    max_pages: Optional[int] = None
    extra_params: Optional[Mapping[str, Any]] = None
    path_override: Optional[str] = None
    endpoint_name: Optional[str] = None


class _RetryPolicy:
    """Evaluate retry behaviour for HTTP responses and request errors."""

    def __init__(self, config: ErrorHandlerConfig) -> None:
        self._config = config
        self._status_ranges: List[tuple[int, int]] = []
        self._status_exact: set[int] = set()

        for spec in config.retry_statuses:
            if spec.endswith("XX"):
                bucket = int(spec[0])
                start = bucket * 100
                self._status_ranges.append((start, start + 99))
            else:
                try:
                    code = int(spec)
                except ValueError:
                    continue
                self._status_exact.add(code)

    def can_retry(self, retries_attempted: int) -> bool:
        return retries_attempted < self._config.max_retries

    def should_retry_status(self, status_code: int) -> bool:
        if status_code in self._status_exact:
            return True
        for start, end in self._status_ranges:
            if start <= status_code <= end:
                return True
        return False

    def should_retry_exception(self, exc: Exception) -> bool:
        if isinstance(exc, httpx.TimeoutException):
            return self._config.retry_on_timeout
        if isinstance(exc, httpx.RequestError):
            return self._config.retry_on_connection_errors
        return False

    def next_delay(self, retries_attempted: int) -> float:
        base = self._config.backoff.initial_delay_seconds
        multiplier = self._config.backoff.multiplier
        delay = base * (multiplier**retries_attempted)
        max_delay = self._config.backoff.max_delay_seconds
        if max_delay > 0:
            delay = min(delay, max_delay)
        return max(delay, 0.0)


@dataclass
class RestClient:
    """HTTP client tailored for REST-to-DataFrame ingestion."""

    base_url: str
    auth: AuthConfig
    timeout: float = 30.0
    options: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        headers = {
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        }
        self._oauth2_token: Optional[str] = None
        if self.auth.type == "bearer" and self.auth.token:
            token_header = f"Bearer {self.auth.token}"
            self._oauth2_token = self.auth.token
            headers["Authorization"] = token_header
        elif self.auth.type == "oauth2":
            access_token = self._obtain_oauth2_token()
            self._oauth2_token = access_token
            token_header = f"Bearer {access_token}"
            headers["Authorization"] = token_header

        self._base_headers = dict(headers)
        self._client = httpx.Client(
            base_url=self.base_url, headers=headers, timeout=self.timeout
        )

    def close(self) -> None:
        self._client.close()

    def fetch_records(
        self,
        stream: StreamConfig,
        *,
        window: Optional[PaginationWindow] = None,
    ) -> Iterator[List[Mapping[str, Any]]]:
        """Yield pages of JSON records for the provided stream definition."""

        for page in self.fetch_pages(stream, window=window):
            yield page.records

    def fetch_pages(
        self,
        stream: StreamConfig,
        *,
        window: Optional[PaginationWindow] = None,
        persist_state: bool = True,
        observe_records: bool = True,
    ) -> Iterator[RestPage]:
        """Yield pages with rich metadata for the provided stream definition."""

        template_context: Dict[str, Any] = {
            "options": dict(self.options or {}),
            "params": dict(stream.params or {}),
            "headers": dict(stream.headers or {}),
            "raw_params": dict(stream.params or {}),
        }

        rendered_params = (
            {
                key: _render_template(value, template_context)
                for key, value in stream.params.items()
            }
            if stream.params
            else {}
        )

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
            pagination_window=window,
            persist_state=persist_state,
            observe_records=observe_records,
        )

    def _obtain_oauth2_token(self) -> str:
        if not self.auth.token_url:
            raise ConfigError("OAuth2 auth requires 'token_url'")
        if not self.auth.client_id:
            raise ConfigError("OAuth2 auth requires 'client_id'")

        client_secret = self.auth.client_secret
        if not client_secret:
            secret = self.options.get("oauth_client_secret") if self.options else None
            if isinstance(secret, str) and secret.strip():
                client_secret = secret.strip()
        if not client_secret:
            raise ConfigError(
                "OAuth2 auth requires a client secret provided via runtime option 'oauth_client_secret'",
            )


        base_payload: Dict[str, Any] = {
            "grant_type": "client_credentials",
            "client_id": self.auth.client_id,
            "client_secret": client_secret,
        }

        # Some OAuth providers (particularly bespoke Spring controllers) expect camelCase keys.
        # Add aliases so both "client_id"/"client_secret" and "clientId"/"clientSecret" are present.
        for canonical_key, alias_key in (("client_id", "clientId"), ("client_secret", "clientSecret")):
            value = base_payload.get(canonical_key)
            if value is not None:
                base_payload.setdefault(alias_key, value)

        if self.auth.scope:
            base_payload["scope"] = " ".join(self.auth.scope)
        if self.auth.audience:
            base_payload["audience"] = self.auth.audience
        if self.auth.extra_params:
            for key, value in self.auth.extra_params.items():
                base_payload[str(key)] = value

        # httpx expects a string-only mapping for form submissions; ensure complex values are serialised.
        form_payload = {
            key: json.dumps(value) if isinstance(value, (list, dict)) else str(value)
            for key, value in base_payload.items()
        }

        def _post_token_request(*, json_mode: bool) -> httpx.Response:
            if json_mode:
                return httpx.post(self.auth.token_url, json=base_payload, timeout=self.timeout)
            return httpx.post(self.auth.token_url, data=form_payload, timeout=self.timeout)

        json_mode_requested = False
        try:
            response = _post_token_request(json_mode=False)
        except httpx.HTTPError as exc:
            raise ConfigError(f"OAuth2 token request failed: {exc}") from exc

        detail = response.text.strip()
        if response.status_code >= 400 and not json_mode_requested:
            try:
                json_mode_requested = True
                response = _post_token_request(json_mode=True)
                detail = response.text.strip()
            except httpx.HTTPError as exc:
                raise ConfigError(f"OAuth2 token request failed: {exc}") from exc

        if response.status_code >= 400:
            mode_hint = "JSON body" if json_mode_requested else "form body"
            raise ConfigError(
                "OAuth2 token request failed with status "
                f"{response.status_code}: {detail or 'no response body'} (token request sent as {mode_hint})",
            )

        try:
            payload = response.json()
        except ValueError as exc:  # pragma: no cover - unexpected server response
            raise ConfigError("OAuth2 token response was not valid JSON") from exc

        access_token = None
        if isinstance(payload, Mapping):
            candidate_keys = (
                "access_token",
                "accessToken",
                "AccessToken",
                "token",
            )
            for key in candidate_keys:
                value = payload.get(key)
                if isinstance(value, str) and value.strip():
                    access_token = value.strip()
                    break

            if access_token is None:
                for key, value in payload.items():
                    if not isinstance(key, str):
                        continue
                    if key.lower().replace("_", "") == "accesstoken" and isinstance(value, str) and value.strip():
                        access_token = value.strip()
                        break

        if not access_token:
            raise ConfigError("OAuth2 token response missing 'access_token'")

        return access_token

    def peek_page(self, stream: StreamConfig) -> Optional[RestPage]:
        """Return the first page without mutating incremental state."""

        generator = self.fetch_pages(
            stream,
            window=PaginationWindow(max_pages=1),
            persist_state=False,
            observe_records=False,
        )
        try:
            return next(generator, None)
        finally:
            try:
                generator.close()
            except Exception:
                pass

    def _iterate_pages(
        self,
        *,
        initial_path: str,
        query_params: Dict[str, Any],
        pagination: PaginationConfig,
        request_headers: Optional[Dict[str, str]],
        stream: StreamConfig,
        declared_schema: Optional[StructType],
        pagination_window: Optional[PaginationWindow] = None,
        persist_state: bool = True,
        observe_records: bool = True,
    ) -> Iterator[RestPage]:
        tracker = _IncrementalTracker(
            base_url=self.base_url,
            stream=stream,
            options=self.options,
        )

        tracker.apply_to_params(query_params)

        retry_policy = _RetryPolicy(stream.error_handler)

        window_page = (
            getattr(pagination_window, "page", None) if pagination_window else None
        )
        window_offset = (
            getattr(pagination_window, "offset", None) if pagination_window else None
        )
        max_pages = (
            getattr(pagination_window, "max_pages", None) if pagination_window else None
        )
        extra_params = (
            dict(pagination_window.extra_params)
            if pagination_window and pagination_window.extra_params
            else {}
        )
        path_override = (
            getattr(pagination_window, "path_override", None)
            if pagination_window
            else None
        )

        base_path = path_override or initial_path

        base_params = dict(query_params)
        if extra_params:
            base_params.update(extra_params)
        query_params = base_params

        next_url: Optional[str] = base_path
        include_params = True

        # Track pagination-specific state between requests.
        offset_value = pagination.start_offset if pagination.type == "offset" else 0
        if window_offset is not None and pagination.type == "offset":
            offset_value = window_offset
        page_number = pagination.start_page if pagination.type == "page" else 1
        if window_page is not None and pagination.type == "page":
            page_number = window_page
        cursor_to_apply: Optional[str] = (
            pagination.initial_cursor if pagination.type == "cursor" else None
        )

        if (
            pagination.type == "offset"
            and pagination.limit_param
            and pagination.page_size is not None
        ):
            query_params.setdefault(pagination.limit_param, pagination.page_size)
        if (
            pagination.type == "page"
            and pagination.limit_param
            and pagination.page_size is not None
        ):
            query_params.setdefault(pagination.limit_param, pagination.page_size)
        if (
            pagination.type == "cursor"
            and pagination.cursor_param
            and cursor_to_apply is not None
        ):
            query_params[pagination.cursor_param] = cursor_to_apply
            cursor_to_apply = None

        pages_emitted = 0

        try:
            while next_url:
                if pagination.type == "offset":
                    offset_param = pagination.offset_param or "offset"
                    query_params[offset_param] = offset_value
                    include_params = True
                elif pagination.type == "page":
                    page_param = pagination.page_param or "page"
                    query_params[page_param] = page_number
                    include_params = True
                    if pagination.limit_param and pagination.page_size is not None:
                        query_params[pagination.limit_param] = pagination.page_size
                elif pagination.type == "cursor":
                    if cursor_to_apply is not None and pagination.cursor_param:
                        query_params[pagination.cursor_param] = cursor_to_apply
                        cursor_to_apply = None
                    include_params = True

                response = self._request_with_retries(
                    url=next_url,
                    query_params=query_params,
                    include_params=include_params,
                    request_headers=request_headers,
                    policy=retry_policy,
                )

                try:
                    payload = response.json()
                except json.JSONDecodeError as exc:
                    raise ValueError("Expected API response to be valid JSON") from exc

                records = _extract_records(
                    payload, stream.record_selector, declared_schema
                )
                if not isinstance(records, list):
                    raise ValueError("Expected API response to be a list of records")

                if observe_records:
                    tracker.observe(records)

                yield RestPage(
                    records=records,
                    payload=payload,
                    url=str(response.url),
                    status_code=response.status_code,
                    headers=dict(response.headers),
                )

                pages_emitted += 1
                if max_pages is not None and pages_emitted >= max_pages:
                    break

                # Advance pagination state based on configured strategy.
                if pagination.type == "none":
                    next_url = None
                elif pagination.type == "link_header":
                    next_url = _next_page(response, pagination)
                    include_params = next_url == base_path if next_url else True
                elif pagination.type == "offset":
                    if pagination.stop_on_empty_response and not records:
                        next_url = None
                    else:
                        step = pagination.page_size or len(records)
                        if step <= 0:
                            next_url = None
                        else:
                            offset_value += step
                            next_url = base_path
                            include_params = True
                elif pagination.type == "page":
                    if pagination.stop_on_empty_response and not records:
                        next_url = None
                    else:
                        page_number += 1
                        next_url = base_path
                        include_params = True
                elif pagination.type == "cursor":
                    next_link = None
                    if pagination.next_url_path:
                        next_link = _first_value_from_path(
                            payload, pagination.next_url_path
                        )
                    if isinstance(next_link, str) and next_link:
                        if pagination.stop_on_empty_response and not records:
                            next_url = None
                            cursor_to_apply = None
                            include_params = False
                        else:
                            parsed = urlparse(next_link)
                            # Include query params only when following a path without its own query.
                            include_params = not (
                                parsed.scheme or parsed.netloc or parsed.query
                            )
                            next_url = next_link
                            cursor_to_apply = None
                    else:
                        next_cursor = _resolve_cursor_value_from_response(
                            response, payload, pagination
                        )
                        if next_cursor in (None, ""):
                            next_url = None
                        else:
                            cursor_to_apply = str(next_cursor)
                            next_url = base_path
                            include_params = True
                            if pagination.stop_on_empty_response and not records:
                                next_url = None
                else:
                    next_url = None
        finally:
            if persist_state:
                tracker.persist()

    def __enter__(self) -> "RestClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _resolve_authorization_header(self) -> Optional[str]:
        """Return the Authorization header value for the current auth context."""

        if self.auth.type == "bearer":
            if not self._oauth2_token and self.auth.token:
                self._oauth2_token = self.auth.token
            token = self._oauth2_token
            return f"Bearer {token}" if token else None

        if self.auth.type == "oauth2":
            if not self._oauth2_token:
                self._oauth2_token = self._obtain_oauth2_token()
            token = self._oauth2_token
            return f"Bearer {token}" if token else None

        return None

    def _request_with_retries(
        self,
        *,
        url: str,
        query_params: Dict[str, Any],
        include_params: bool,
        request_headers: Optional[Dict[str, str]],
        policy: _RetryPolicy,
    ) -> httpx.Response:
        retries_attempted = 0
        while True:
            try:
                final_headers = dict(self._base_headers)
                if request_headers:
                    for header_key, header_value in request_headers.items():
                        if header_value is None:
                            continue
                        final_headers[header_key] = str(header_value)

                request = self._client.build_request(
                    "GET",
                    url,
                    params=query_params if include_params else None,
                    headers=final_headers,
                )

                manual_auth_header: Optional[str] = None
                for key, value in request.headers.items():
                    if key.lower() == "authorization" and value:
                        manual_auth_header = value
                        break

                effective_auth = manual_auth_header or self._resolve_authorization_header()
                if effective_auth:
                    request.headers["Authorization"] = effective_auth

                response = self._client.send(request)
            except (httpx.TimeoutException, httpx.RequestError) as exc:
                if policy.should_retry_exception(exc) and policy.can_retry(
                    retries_attempted
                ):
                    delay = policy.next_delay(retries_attempted)
                    retries_attempted += 1
                    if delay > 0:
                        time.sleep(delay)
                    continue
                raise RuntimeError(f"Request to {url} failed: {exc}") from exc

            status_code = response.status_code
            if status_code >= 400:
                if policy.should_retry_status(status_code) and policy.can_retry(
                    retries_attempted
                ):
                    delay = policy.next_delay(retries_attempted)
                    retries_attempted += 1
                    response.close()
                    if delay > 0:
                        time.sleep(delay)
                    continue

                message = _summarise_response_error(response)
                request_auth = response.request.headers.get("Authorization")
                if not request_auth:
                    request_auth = response.request.headers.get("authorization")
                if request_auth:
                    message = f"{message} [Authorization header present]"
                else:
                    message = f"{message} [Authorization header missing]"
                response.close()
                raise RuntimeError(
                    f"Request to {response.url} failed with status {status_code}: {message}"
                )

            return response


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
            return {
                key: _cast_value(val, datatype.valueType) for key, val in value.items()
            }
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


def _first_value_from_path(payload: Any, path: Iterable[str]) -> Any:
    if not path:
        return None
    try:
        values = _select_field_path(payload, path)
    except Exception:
        return None
    for value in values:
        if value in (None, ""):
            continue
        if isinstance(value, list):
            for item in value:
                if item not in (None, ""):
                    return item
        else:
            return value
    return None


def _resolve_cursor_value_from_response(
    response: httpx.Response,
    payload: Any,
    pagination: PaginationConfig,
) -> Any:
    candidates: List[Any] = []

    if pagination.cursor_path:
        try:
            candidates.extend(_select_field_path(payload, pagination.cursor_path))
        except Exception:
            pass

    if pagination.cursor_header:
        header_value = response.headers.get(pagination.cursor_header)
        if header_value:
            candidates.append(header_value)

    for candidate in candidates:
        if candidate in (None, ""):
            continue
        if isinstance(candidate, list):
            for item in candidate:
                if item not in (None, ""):
                    return item
        else:
            return candidate

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


class _IncrementalTracker:
    """Handle incremental cursor seeding and persistence across runs."""

    def __init__(
        self,
        *,
        base_url: str,
        stream: StreamConfig,
        options: Mapping[str, Any],
    ) -> None:
        self._stream = stream
        self._options = options
        self._base_url = base_url.rstrip("/")
        self._cursor_param = stream.incremental.cursor_param
        self._cursor_field = stream.incremental.cursor_field
        self._enabled = bool(self._cursor_param and self._cursor_field)

        state_path = self._options.get("incremental_state_path")
        self._state_file: Optional[Path]
        self._state_remote_path: Optional[str]
        if state_path and isinstance(state_path, str):
            parsed = urlparse(state_path)
            if parsed.scheme in {"", "file"}:
                resolved = parsed.path if parsed.scheme == "file" else state_path
                self._state_file = Path(resolved)
                self._state_remote_path = None
            else:
                self._state_file = None
                self._state_remote_path = state_path
        else:
            self._state_file = None
            self._state_remote_path = None

        state_key = self._options.get("incremental_state_key")
        if isinstance(state_key, str) and state_key.strip():
            self._state_key = state_key.strip()
        else:
            self._state_key = f"{self._stream.name}@{self._base_url}"

        mem_option = self._options.get("incremental_memory_state")
        if mem_option is None:
            self._memory_enabled = True
        else:
            self._memory_enabled = _coerce_to_bool(mem_option)

        self._initial_value: Optional[str] = None
        self._latest_value: Optional[str] = None

        if self._enabled:
            self._initial_value = self._load_state_value()
            if self._initial_value is None:
                fallback = self._options.get("incremental_start_value")
                if fallback is not None:
                    self._initial_value = str(fallback)

    def apply_to_params(self, params: Dict[str, Any]) -> None:
        if (
            not self._enabled
            or self._initial_value is None
            or self._cursor_param is None
        ):
            return
        params.setdefault(self._cursor_param, self._initial_value)

    def observe(self, records: Iterable[Mapping[str, Any]]) -> None:
        if not self._enabled or self._cursor_field is None:
            return
        for record in records:
            if not isinstance(record, Mapping):
                continue
            value = _extract_cursor_value(record, self._cursor_field)
            if value is None:
                continue
            self._latest_value = str(value)

    def persist(self) -> None:
        if not self._enabled:
            return
        if self._latest_value is None:
            return
        if self._initial_value == self._latest_value:
            return
        entry = self._build_entry(self._latest_value)
        if self._state_file is not None or self._state_remote_path is not None:
            self._write_state_value(entry)
        if self._memory_enabled:
            _MEMORY_STATE[self._state_key] = entry

    def _load_state_value(self) -> Optional[str]:
        file_value = self._load_state_file_value()
        if file_value is not None:
            return file_value
        if self._memory_enabled:
            entry = _MEMORY_STATE.get(self._state_key)
            if isinstance(entry, Mapping):
                value = entry.get("cursor_value")
                if value is not None:
                    return str(value)
        return None

    def _load_state_file_value(self) -> Optional[str]:
        payload = self._load_state_payload()
        if not payload:
            return None

        entry: Any
        streams = payload.get("streams")
        if isinstance(streams, dict):
            entry = streams.get(self._state_key)
        else:
            entry = payload.get(self._state_key)

        if isinstance(entry, dict):
            value = entry.get("cursor_value") or entry.get("value")
            return str(value) if value is not None else None
        if entry is not None:
            return str(entry)
        return None

    def _write_state_value(self, entry: Dict[str, Any]) -> None:
        if self._state_file is None and self._state_remote_path is None:
            return

        payload = self._load_state_payload()

        streams = payload.get("streams")
        if not isinstance(streams, dict):
            streams = {}
        payload["streams"] = streams

        streams[self._state_key] = entry

        data = json.dumps(payload, indent=2, sort_keys=True)

        if self._state_file is not None:
            state_dir = self._state_file.parent
            if state_dir and not state_dir.exists():
                state_dir.mkdir(parents=True, exist_ok=True)

            tmp_path = self._state_file.with_suffix(self._state_file.suffix + ".tmp")
            tmp_path.write_text(data)
            tmp_path.replace(self._state_file)
        elif self._state_remote_path is not None:
            _write_remote_text(self._state_remote_path, data)

    def _build_entry(self, value: str) -> Dict[str, Any]:
        return {
            "cursor_param": self._cursor_param,
            "cursor_field": self._cursor_field,
            "cursor_value": value,
            "mode": self._stream.incremental.mode,
            "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }

    def _load_state_payload(self) -> Dict[str, Any]:
        if self._state_file is not None:
            if not self._state_file.exists():
                return {}
            try:
                existing = json.loads(self._state_file.read_text())
                if isinstance(existing, dict):
                    return existing
            except (json.JSONDecodeError, OSError):
                return {}
            return {}
        if self._state_remote_path is not None:
            return _read_remote_json(self._state_remote_path)
        return {}


def _extract_cursor_value(record: Mapping[str, Any], field: str) -> Any:
    parts = field.split(".") if field else [field]
    current: Any = record
    for part in parts:
        if not part:
            return None
        if isinstance(current, Mapping):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def _read_remote_json(path: str) -> Dict[str, Any]:
    fs, remote_path = _get_remote_filesystem(path)
    try:
        if hasattr(fs, "exists") and not fs.exists(remote_path):
            return {}
        with fs.open(remote_path, mode="r") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return {}
    except Exception as exc:  # pragma: no cover - depends on backend
        raise RuntimeError(
            f"Failed to read incremental state from {path}: {exc}"
        ) from exc

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    if isinstance(payload, dict):
        return payload
    return {}


def _write_remote_text(path: str, data: str) -> None:
    fs, remote_path = _get_remote_filesystem(path)
    directory = posixpath.dirname(remote_path)

    try:
        if directory and directory not in {"", "/"}:
            if hasattr(fs, "makedirs"):
                fs.makedirs(directory, exist_ok=True)
            elif hasattr(fs, "mkdir"):
                try:
                    fs.mkdir(directory, create_parents=True)
                except TypeError:  # older signatures
                    fs.mkdir(directory)
                except FileExistsError:
                    pass
    except Exception as exc:  # pragma: no cover - depends on backend
        raise RuntimeError(
            f"Failed to prepare incremental state directory for {path}: {exc}"
        ) from exc

    try:
        with fs.open(remote_path, mode="w") as handle:
            handle.write(data)
    except Exception as exc:  # pragma: no cover - depends on backend
        raise RuntimeError(
            f"Failed to write incremental state to {path}: {exc}"
        ) from exc


def _get_remote_filesystem(path: str):
    try:
        import fsspec  # type: ignore
    except ImportError as exc:  # pragma: no cover - guard rails
        raise RuntimeError(
            "fsspec is required to use non-local incremental_state_path values"
        ) from exc

    fs, remote_path = fsspec.core.url_to_fs(path)
    return fs, remote_path


def _summarise_response_error(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except (json.JSONDecodeError, ValueError):
        payload = None

    if isinstance(payload, Mapping):
        for key in ("detail", "message", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
            if isinstance(first, Mapping):
                nested = first.get("message") or first.get("detail")
                if isinstance(nested, str) and nested.strip():
                    return nested.strip()

    text = response.text.strip()
    if text:
        snippet = text
        if "<html" in text.lower():
            # Roughly strip HTML tags to surface human-readable content.
            snippet = re.sub(r"<[^>]+>", " ", text)
        snippet = " ".join(snippet.split())  # collapse whitespace
        if len(snippet) > 300:
            return snippet[:297] + "..."
        return snippet
    return "no details provided"
