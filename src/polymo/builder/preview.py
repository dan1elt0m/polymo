"""Run the generated fetch core in-process for builder previews."""

from __future__ import annotations

from itertools import islice
from typing import Any, Dict, List, Optional, Tuple

from ..codegen import generate_core
from ..config import RestSourceConfig


def run_preview(
    config: RestSourceConfig, *, token: Optional[str], limit: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Optional[str]]:
    """Execute the generated `fetch_records` in-process and capture raw pages.

    Runs the same code the builder's "Generate script" action produces
    (`generate_core`), so the preview reflects exactly what a downloaded
    script would fetch. Returns `(records, raw_pages, error)`, where
    `raw_pages` mirrors the HTTP responses seen by `_request` and `error` is
    the stringified exception (if any) raised while collecting records —
    records/raw_pages collected before the failure are still returned so the
    "Raw API" tab can show what happened.
    """
    code = generate_core(config)
    namespace: Dict[str, Any] = {}
    exec(compile(code, "<polymo-preview>", "exec"), namespace)  # noqa: S102

    if token:
        namespace["API_TOKEN"] = token  # bearer
        namespace["CLIENT_SECRET"] = token  # oauth2 (harmless if unused)

    raw_pages: List[Dict[str, Any]] = []
    original_request = namespace["_request"]

    def recording_request(session, url, params):
        response = original_request(session, url, params)
        try:
            payload = response.json()
        except ValueError:
            payload = response.text
        raw_pages.append(
            {
                "url": str(response.url),
                "status_code": response.status_code,
                "payload": payload,
            }
        )
        return response

    namespace["_request"] = recording_request

    # Windowed configs (partition_strategy in {"param_range", "endpoints"})
    # emit a literal WINDOWS list; the builder preview blends records across
    # windows, in order, until `limit` is reached (or the windows run out),
    # stopping early so later windows aren't hit once the limit is met.
    windows = namespace.get("WINDOWS")
    records: List[Dict[str, Any]] = []
    error: Optional[str] = None
    try:
        if windows:
            for window in windows:
                if len(records) >= limit:
                    break
                remaining = limit - len(records)
                records.extend(islice(namespace["fetch_records"](**window), remaining))
        else:
            # `records.extend(...)` (not `records = list(...)`) so a
            # mid-generator failure still leaves whatever was already
            # yielded in place — `list(iterable)` discards its in-progress
            # result entirely if the iterable raises before completing.
            records.extend(islice(namespace["fetch_records"](), limit))
    except Exception as exc:  # noqa: BLE001 - surfaced to caller as `error`
        error = str(exc)

    return records, raw_pages, error
