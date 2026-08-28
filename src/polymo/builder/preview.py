"""Run the generated fetch core in-process for builder previews."""

from __future__ import annotations

from itertools import islice
from typing import Any, Dict, List, Optional, Tuple

from ..codegen import generate_core
from ..config import RestSourceConfig


def run_preview(
    config: RestSourceConfig, *, token: Optional[str], limit: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Execute the generated `fetch_records` in-process and capture raw pages.

    Runs the same code the builder's "Generate script" action produces
    (`generate_core`), so the preview reflects exactly what a downloaded
    script would fetch. Returns `(records, raw_pages)` where `raw_pages`
    mirrors the HTTP responses seen by `_request`.
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
    # emit a literal WINDOWS list; the builder preview only samples the
    # first window rather than fetching every partition.
    windows = namespace.get("WINDOWS")
    if windows:
        records = list(islice(namespace["fetch_records"](**windows[0]), limit))
    else:
        records = list(islice(namespace["fetch_records"](), limit))

    return records, raw_pages
