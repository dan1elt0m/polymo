"""Run the generated fetch core in-process for builder previews."""

from __future__ import annotations

import json
import re
from itertools import islice
from typing import Any, Dict, List, Optional, Tuple

from ..codegen import generate_core
from ..config import RestSourceConfig

# Matches a module-level `<VAR>: str = _dbx_secret(...)` assignment for one
# of the four secret-ref slot kinds the generator can emit (API_TOKEN /
# API_KEY / CLIENT_SECRET, and any OPT_* option placeholder). Anchored to
# line start via MULTILINE so it only ever matches the assignment itself.
_DBX_SECRET_ASSIGNMENT_RE = re.compile(
    r"^(?P<var>API_TOKEN|API_KEY|CLIENT_SECRET|OPT_[A-Za-z0-9_]*): str = "
    r"_dbx_secret\([^\n]*\)$",
    re.MULTILINE,
)

# Slot variables a preview `token` can actually stand in for (mirrors the
# post-exec namespace injection below). OPT_* option placeholders have no
# override mechanism in preview at all, secret-backed or not.
_TOKEN_OVERRIDABLE_VARS = frozenset({"API_TOKEN", "API_KEY", "CLIENT_SECRET"})


def _substitute_secret_refs(code: str, token: Optional[str]) -> str:
    """Source-substitute `_dbx_secret(...)` call sites before `exec`.

    A module-level `_dbx_secret(...)` call executes during `exec` and would
    raise `RuntimeError` outside Databricks (no active Spark session) — so
    it can never be left in place for preview. Instead, each matching
    assignment line is rewritten to a literal pre-exec: the auth slot
    (API_TOKEN/API_KEY/CLIENT_SECRET) that matches the supplied `token`, if
    any, gets that real value; every other secret-ref variable — including
    every OPT_* option placeholder, which has no override path in preview —
    gets the same `"REPLACE_ME"` dummy the unresolved-placeholder path
    already defaults to, so `exec` succeeds and the request just sends a
    dummy value.
    """

    def _replace(match: "re.Match[str]") -> str:
        var = match.group("var")
        value = token if (token and var in _TOKEN_OVERRIDABLE_VARS) else "REPLACE_ME"
        return f"{var}: str = {json.dumps(value)}"

    return _DBX_SECRET_ASSIGNMENT_RE.sub(_replace, code)


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
    code = _substitute_secret_refs(code, token)
    namespace: Dict[str, Any] = {}
    exec(compile(code, "<polymo-preview>", "exec"), namespace)  # noqa: S102

    if token:
        namespace["API_TOKEN"] = token  # bearer
        namespace["CLIENT_SECRET"] = token  # oauth2 (harmless if unused)
        namespace["API_KEY"] = token  # api_key (harmless if unused)

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


def _infer_field_types(records: List[Dict[str, Any]]) -> Dict[str, str]:
    """Vote a Spark type per column across `records`; the shared core of
    `infer_ddl_from_records` (also used by `_get_preview_df` in `app.py` to
    know which columns need numeric coercion before `createDataFrame`).

    Mirrors `_infer_schema` in `codegen/templates/core.py.jinja` — keep the
    two in sync. That template function is baked into every *generated*
    script (so it can re-sample the live API at run time), while this one
    runs against the preview records the builder UI already fetched.

    One deliberate difference from the template: a column whose value is
    `None` in every sampled record casts no type vote there, so the
    template's `_infer_schema` just omits it from the DDL entirely (dropping
    the column). That's fine for a generated script, which raises loudly if
    sampling ever comes up completely empty. For the builder preview it
    means the column silently vanishes from `dtypes` instead of showing up
    as unknown/empty — worse, unqualified `spark.createDataFrame(records)`
    (no schema at all) actually *crashes* with `[CANNOT_DETERMINE_TYPE]` in
    this situation, which is the bug this function exists to fix (typical
    for XML APIs, where an always-empty element decodes to `None` on every
    record). So here, a no-vote column defaults to STRING instead of being
    dropped.
    """
    columns: Dict[str, Optional[str]] = {}
    for record in records:
        for key, value in record.items():
            columns.setdefault(key, None)
            if value is None:
                continue
            if isinstance(value, bool):
                candidate = "BOOLEAN"
            elif isinstance(value, int):
                candidate = "BIGINT"
            elif isinstance(value, float):
                candidate = "DOUBLE"
            else:
                candidate = "STRING"
            current = columns[key]
            if current is None:
                columns[key] = candidate
            elif current == candidate:
                pass
            elif {current, candidate} == {"BIGINT", "DOUBLE"}:
                columns[key] = "DOUBLE"
            else:
                columns[key] = "STRING"
    return {name: type_ or "STRING" for name, type_ in columns.items()}


def infer_ddl_from_records(records: List[Dict[str, Any]]) -> str:
    """Infer a Spark DDL schema string from already-collected preview records.

    See `_infer_field_types` for the voting rules this applies.
    """
    fields = _infer_field_types(records)
    return ", ".join(f"`{name}` {type_}" for name, type_ in fields.items())
