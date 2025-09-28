"""Minimal REST client capable of streaming pages for the connector."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional

import httpx

from .config import AuthConfig, PaginationConfig, StreamConfig


USER_AGENT = "polymo-rest-source/0.1"


@dataclass
class RestClient:
    """Thin HTTP client tailored for REST-to-DataFrame ingestion."""

    base_url: str
    auth: AuthConfig
    timeout: float = 30.0

    def __post_init__(self) -> None:
        headers = {"User-Agent": USER_AGENT}
        if self.auth.type == "bearer" and self.auth.token:
            headers["Authorization"] = f"Bearer {self.auth.token}"

        self._client = httpx.Client(base_url=self.base_url, headers=headers, timeout=self.timeout)

    def close(self) -> None:
        self._client.close()

    def fetch_records(self, stream: StreamConfig) -> Iterator[List[Mapping[str, Any]]]:
        """Yield pages of JSON records for the provided stream definition."""

        formatter = _PathFormatter(stream.params)
        path = formatter.render(stream.path)

        query_params = formatter.remaining_params()
        pagination = stream.pagination

        next_url: Optional[str] = path

        while next_url:
            response = self._client.get(next_url, params=query_params if next_url == path else None)
            response.raise_for_status()
            payload = response.json()

            records = _normalise_payload(payload)
            if not isinstance(records, list):
                raise ValueError("Expected API response to be a list of records")

            yield records

            next_url = _next_page(response, pagination)

    def __enter__(self) -> "RestClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def _normalise_payload(payload: Any) -> Any:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        # Accept top-level "data" or "items" wrappers.
        for key in ("data", "items", "results"):
            if key in payload and isinstance(payload[key], list):
                return payload[key]
    return payload


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

