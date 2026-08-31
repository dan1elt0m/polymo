"""FastAPI application powering the polymo web builder."""

from __future__ import annotations

import json
from functools import partial
from importlib import metadata, resources
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote, quote_plus

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from ..codegen import CodegenError, generate, generate_bundle
from ..codegen.generator import _identifier
from ..config import ConfigError, RestSourceConfig, config_to_dict, parse_config
from . import databricks
from .preview import run_preview

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pyspark.sql import SparkSession

PACKAGE_ROOT = resources.files(__package__)
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_ROOT.joinpath("templates")))
STATIC_PATH = PACKAGE_ROOT.joinpath("static")


class ValidationRequest(BaseModel):
    config_dict: Dict[str, Any] = Field(
        description="Configuration provided as a dictionary"
    )
    token: Optional[str] = Field(
        None, description="Bearer token supplied separately (not stored)"
    )
    options: Optional[Dict[str, Any]] = Field(
        default=None, description="Spark reader options provided alongside the config"
    )

    model_config = ConfigDict(extra="ignore")


class ValidationResponse(BaseModel):
    valid: bool
    stream: str | None = None
    message: Optional[str] = None
    config: Optional[Dict[str, Any]] = None


class SampleRequest(BaseModel):
    config_dict: Dict[str, Any]
    token: Optional[str] = None
    limit: int = Field(20, ge=1, le=500, description="Maximum records to preview")
    options: Optional[Dict[str, Any]] = Field(
        default=None, description="Spark reader options provided alongside the config"
    )

    model_config = ConfigDict(extra="ignore")


class SampleResponse(BaseModel):
    stream: str
    records: List[Dict[str, Any]]
    dtypes: List[Dict[str, str]] = Field(
        default_factory=list, description="Spark column data types"
    )
    raw_pages: List[Dict[str, Any]] = Field(
        default_factory=list, description="Raw REST API responses captured per page"
    )
    rest_error: Optional[str] = None


class GenerateRequest(BaseModel):
    config_dict: Dict[str, Any]

    model_config = ConfigDict(extra="ignore")


class GenerateResponse(BaseModel):
    script: str
    stream: str


class BootstrapRequest(BaseModel):
    config_dict: Dict[str, Any]
    project_dir: str
    project_name: str
    catalog: str
    schema_: str = Field(alias="schema")
    overwrite: bool = False

    model_config = ConfigDict(extra="ignore", populate_by_name=True)


class BootstrapResponse(BaseModel):
    project_path: str
    files: List[str]


class DeployRequest(BaseModel):
    project_path: str
    profile: Optional[str] = None
    target: str = "dev"

    model_config = ConfigDict(extra="ignore")


class RunRequest(BaseModel):
    project_path: str
    profile: Optional[str] = None
    target: str = "dev"

    model_config = ConfigDict(extra="ignore")


class CommandResponse(BaseModel):
    ok: bool
    output: str


def _polymo_version() -> str:
    try:
        return metadata.version("polymo")
    except metadata.PackageNotFoundError:  # pragma: no cover - dev installs
        return "dev"


def create_app() -> FastAPI:
    app = FastAPI(title="polymo builder", version=_polymo_version())

    app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> (
        FileResponse
    ):  # pragma: no cover - static convenience endpoint
        return FileResponse(STATIC_PATH / "favicon.ico")

    @app.get("/apple-touch-icon.png", include_in_schema=False)
    @app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
    async def apple_touch_icon() -> (
        FileResponse
    ):  # pragma: no cover - static convenience endpoint
        # Re-use existing high-res logo as apple touch icon
        return FileResponse(STATIC_PATH / "logo192.png")

    @app.get("/")
    async def index(request: Request) -> Any:
        return TEMPLATES.TemplateResponse(request, "index.html")

    @app.post("/api/validate", response_model=ValidationResponse)
    async def validate_config(payload: ValidationRequest) -> ValidationResponse:
        try:
            config = _load_config_payload(
                payload.config_dict, payload.token, payload.options
            )
        except ConfigError as exc:
            return ValidationResponse(valid=False, stream=None, message=str(exc))
        except ValueError as exc:
            return ValidationResponse(valid=False, stream=None, message=str(exc))

        config_dict = config_to_dict(config)
        return ValidationResponse(
            valid=True,
            stream=config.stream.name,
            message="Configuration is valid",
            config=config_dict,
        )

    @app.post("/api/sample", response_model=SampleResponse)
    async def sample_records(payload: SampleRequest) -> SampleResponse:
        try:
            config = _load_config_payload(
                payload.config_dict, payload.token, payload.options
            )
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        stream_config = config.stream

        # The session secret (bearer token / api_key / oauth2 client secret)
        # that will actually go out on the wire, resolved the same way
        # `_collect_rest_preview`/`_collect_records` resolve it internally.
        # Computed once here so the redaction pass below and the fetch calls
        # agree on exactly what counts as "the secret".
        secret = _resolve_preview_token(config, payload.token)
        needles: List[str] = []
        if secret is not None and len(secret) >= _MIN_REDACTABLE_SECRET_LENGTH:
            needles = _secret_redaction_needles(secret)

        raw_pages, rest_error = await run_in_threadpool(
            partial(_collect_rest_preview, config, payload.limit, payload.token)
        )
        if needles:
            raw_pages = _redact_secret(raw_pages, needles)
            if rest_error:
                rest_error = _redact_secret(rest_error, needles)

        if rest_error:
            return SampleResponse(
                stream=stream_config.name,
                records=[],
                dtypes=[],
                raw_pages=raw_pages,
                rest_error=rest_error,
            )

        try:
            records, dtypes = await run_in_threadpool(
                partial(_collect_records, config, payload.token, payload.limit)
            )
        except Exception as exc:  # pragma: no cover - surfaced to UI
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        if needles:
            records = _redact_secret(records, needles)

        return SampleResponse(
            stream=stream_config.name,
            records=records,
            dtypes=dtypes,
            raw_pages=raw_pages,
            rest_error=None,
        )

    @app.post("/api/generate", response_model=GenerateResponse)
    async def generate_script(payload: GenerateRequest) -> GenerateResponse:
        try:
            config = parse_config(payload.config_dict)
            script = generate(config)
        except (ConfigError, CodegenError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return GenerateResponse(script=script, stream=config.stream.name)

    @app.get("/api/meta")
    async def get_meta() -> Dict[str, str]:
        return {"version": _polymo_version()}

    @app.get("/api/databricks/profiles")
    async def list_databricks_profiles() -> Dict[str, List[str]]:
        return {"profiles": databricks.list_profiles()}

    @app.get("/api/databricks/catalogs")
    async def list_databricks_catalogs(
        profile: Optional[str] = Query(None),
    ) -> Dict[str, List[str]]:
        data = await run_in_threadpool(
            _run_databricks_cli, ["catalogs", "list"], profile
        )
        return {
            "catalogs": databricks.extract_names(
                data, wrapper_keys=("catalogs",), item_key="name"
            )
        }

    @app.get("/api/databricks/schemas")
    async def list_databricks_schemas(
        catalog: str = Query(...),
        profile: Optional[str] = Query(None),
    ) -> Dict[str, List[str]]:
        data = await run_in_threadpool(
            _run_databricks_cli, ["schemas", "list", catalog], profile
        )
        return {
            "schemas": databricks.extract_names(
                data, wrapper_keys=("schemas",), item_key="name"
            )
        }

    @app.get("/api/databricks/secret-scopes")
    async def list_databricks_secret_scopes(
        profile: Optional[str] = Query(None),
    ) -> Dict[str, List[str]]:
        data = await run_in_threadpool(
            _run_databricks_cli, ["secrets", "list-scopes"], profile
        )
        return {
            "secret_scopes": databricks.extract_names(
                data, wrapper_keys=("scopes",), item_key="name"
            )
        }

    @app.get("/api/databricks/secret-keys")
    async def list_databricks_secret_keys(
        scope: str = Query(...),
        profile: Optional[str] = Query(None),
    ) -> Dict[str, List[str]]:
        data = await run_in_threadpool(
            _run_databricks_cli, ["secrets", "list-secrets", scope], profile
        )
        return {
            "secret_keys": databricks.extract_names(
                data, wrapper_keys=("secrets",), item_key="key"
            )
        }

    @app.post("/api/databricks/bootstrap", response_model=BootstrapResponse)
    async def bootstrap_databricks_project(
        payload: BootstrapRequest,
    ) -> BootstrapResponse:
        target = _resolve_bootstrap_path(payload.project_dir, payload.project_name)

        try:
            config = parse_config(payload.config_dict)
            bundle_files = generate_bundle(
                config,
                project_name=payload.project_name,
                catalog=payload.catalog,
                schema=payload.schema_,
            )
        except (ConfigError, CodegenError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        if target.exists() and any(target.iterdir()) and not payload.overwrite:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"{target} already exists and is not empty; "
                    "pass overwrite=true to replace its contents"
                ),
            )

        written = await run_in_threadpool(_write_bundle_files, target, bundle_files)
        return BootstrapResponse(project_path=str(target), files=written)

    @app.post("/api/databricks/deploy", response_model=CommandResponse)
    async def deploy_databricks_bundle(payload: DeployRequest) -> CommandResponse:
        project_path = _require_bundle_project(payload.project_path)
        return await run_in_threadpool(
            _run_databricks_cli_text,
            ["bundle", "deploy", "-t", payload.target],
            payload.profile,
            project_path,
        )

    @app.post("/api/databricks/run", response_model=CommandResponse)
    async def run_databricks_pipeline(payload: RunRequest) -> CommandResponse:
        project_path = _require_bundle_project(payload.project_path)
        pipeline_key = _read_pipeline_key(project_path)
        return await run_in_threadpool(
            _run_databricks_cli_text,
            ["bundle", "run", pipeline_key, "-t", payload.target],
            payload.profile,
            project_path,
        )

    return app


def _polymo_package_dir() -> Path:
    """Resolved install directory of the `polymo` package.

    Looked up as a plain module-level function (not a constant computed at
    import time) so tests can monkeypatch it to exercise the bootstrap
    path-safety check without depending on where `polymo` actually happens
    to be installed in the test environment.
    """
    return Path(str(resources.files("polymo"))).resolve()


def _resolve_bootstrap_path(project_dir: str, project_name: str) -> Path:
    """Compute (and safety-check) the bootstrap target directory.

    Target is `<project_dir>/<sanitized project_name>`, using the same
    `_identifier()` sanitization `generate_bundle` applies to the package
    name, so the directory name matches `src/<pkg>` inside it. Refuses to
    resolve to the user's home directory, the filesystem root, or anywhere
    inside the installed `polymo` package itself.
    """
    base_dir = Path(project_dir).expanduser().resolve()
    target = base_dir / _identifier(project_name)

    home = Path.home().resolve()
    if target == home or target == Path(target.anchor):
        raise HTTPException(
            status_code=400,
            detail=f"refusing to bootstrap a project into {target}",
        )

    package_dir = _polymo_package_dir()
    if target == package_dir or package_dir in target.parents:
        raise HTTPException(
            status_code=400,
            detail=(
                "refusing to bootstrap a project inside the polymo package "
                f"directory ({package_dir})"
            ),
        )

    return target


def _write_bundle_files(target: Path, files: Dict[str, str]) -> List[str]:
    """Write `generate_bundle`'s output under `target`, returning relpaths written."""
    target.mkdir(parents=True, exist_ok=True)
    written: List[str] = []
    for relpath, content in files.items():
        path = target / relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        written.append(relpath)
    return sorted(written)


def _require_bundle_project(project_path: str) -> Path:
    """Resolve `project_path` and confirm it looks like a bootstrapped bundle.

    Deploy/run both need `databricks.yml` (for `bundle deploy`/`bundle run`
    to work at all) and `.polymo-bundle.json` (run needs its `pipeline_key`)
    — checking both up front gives a clear 400 instead of a confusing CLI
    failure or manifest-read error deeper in the flow.
    """
    path = Path(project_path).expanduser().resolve()
    if (
        not (path / "databricks.yml").is_file()
        or not (path / ".polymo-bundle.json").is_file()
    ):
        raise HTTPException(
            status_code=400, detail=f"{path} is not a polymo bundle project"
        )
    return path


def _read_pipeline_key(project_path: Path) -> str:
    manifest_path = project_path / ".polymo-bundle.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=400, detail=f"could not read {manifest_path}: {exc}"
        ) from exc

    pipeline_key = manifest.get("pipeline_key") if isinstance(manifest, dict) else None
    if not pipeline_key:
        raise HTTPException(
            status_code=400, detail=f"{manifest_path} is missing 'pipeline_key'"
        )
    return str(pipeline_key)


def _run_databricks_cli_text(
    args: List[str], profile: Optional[str], cwd: Path
) -> CommandResponse:
    """Run a `databricks` CLI text command (`bundle deploy`/`bundle run`).

    - Missing CLI executable -> 501, matching `_run_databricks_cli`'s
      "install the CLI" signal for the read endpoints.
    - Non-zero exit / timeout -> NOT an HTTP error: the UI treats deploy/run
      failures as a command result to display, so this returns
      `CommandResponse(ok=False, output=<detail>)` with a 200 status.
    """
    try:
        output = databricks.run_cli_text(args, profile=profile, cwd=cwd)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=501, detail=databricks.CLI_NOT_FOUND_DETAIL
        ) from exc
    except databricks.DatabricksCliError as exc:
        return CommandResponse(ok=False, output=exc.stderr or str(exc))
    return CommandResponse(ok=True, output=output)


def _run_databricks_cli(args: List[str], profile: Optional[str]) -> Any:
    """Run a `databricks` CLI read command, mapping failures to HTTP errors.

    - Missing CLI executable -> 501, so the UI can distinguish "install the
      CLI" from an actual command failure.
    - Non-zero exit / timeout -> 502 with a short stderr-derived detail.
    """
    try:
        return databricks.run_cli(args, profile=profile)
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=501, detail=databricks.CLI_NOT_FOUND_DETAIL
        ) from exc
    except databricks.DatabricksCliError as exc:
        detail = exc.stderr or str(exc)
        raise HTTPException(status_code=502, detail=detail) from exc


def _load_config_payload(
    config_dict: Dict[str, Any],
    token: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
) -> RestSourceConfig:
    return parse_config(config_dict, token=token, options=options)


_REDACTED_MARKER = "***REDACTED***"

# Session secrets under this length are not redacted: a 1-3 char "secret"
# is common enough as an unrelated substring (an id, a short field value)
# that blind substring replacement would mangle legitimate preview output
# for essentially no confidentiality benefit.
_MIN_REDACTABLE_SECRET_LENGTH = 4


def _secret_redaction_needles(secret: str) -> List[str]:
    """Expand a raw secret into every substring form it might come back as.

    A secret placed in a query string (api_key/query auth) doesn't reach
    the wire raw — `requests` percent-encodes it before sending, and
    `raw_pages[*]["url"]` echoes back `response.url`, i.e. the already
    *encoded* value. A raw-substring-only redact would miss it whenever
    the secret contains a URL-reserved character (space, `+`, `/`, `=`,
    `%`, ...). This returns the raw secret plus its `quote(secret,
    safe="")` and `quote_plus(secret)` forms — the two encodings `requests`
    itself uses for path/query components — deduped and with anything
    under `_MIN_REDACTABLE_SECRET_LENGTH` dropped (an encoded form can't
    end up shorter than the raw one, but each needle is checked on its own
    terms rather than relying on that).
    """
    seen: set[str] = set()
    needles: List[str] = []
    for variant in (secret, quote(secret, safe=""), quote_plus(secret)):
        if len(variant) < _MIN_REDACTABLE_SECRET_LENGTH or variant in seen:
            continue
        seen.add(variant)
        needles.append(variant)
    return needles


def _redact_secret(value: Any, needles: Sequence[str]) -> Any:
    """Recursively replace every occurrence of any `needles` entry in
    `value`'s strings.

    Best-effort, presentation-layer masking for `/api/sample`: some target
    APIs echo the credential they were sent back in their response body
    (echo/debug endpoints) or, for query-placed api_key auth, in the
    request URL itself — either would otherwise leak the user's session
    token straight back into the builder's preview UI. This only catches
    the exact substrings in `needles` (see `_secret_redaction_needles` for
    which forms of the secret those cover); a base64-encoded, hashed, or
    otherwise transformed rendering of it downstream is out of scope and
    will not be caught (e.g. the secret is *not* re-derived from a "Basic
    <token>" header value — a plain substring match already handles that
    case since the token itself still appears verbatim).

    Dicts and lists are walked recursively (redacting values, not keys);
    strings have every needle replaced; every other scalar type (int,
    float, bool, None) is returned unchanged.
    """
    if isinstance(value, dict):
        return {key: _redact_secret(item, needles) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact_secret(item, needles) for item in value]
    if isinstance(value, str):
        redacted = value
        for needle in needles:
            redacted = redacted.replace(needle, _REDACTED_MARKER)
        return redacted
    return value


def _resolve_preview_token(
    config: RestSourceConfig, token: Optional[str]
) -> Optional[str]:
    """Fall back to a token embedded in the config's auth block, if any.

    The builder passes the token supplied by the UI separately from the
    config_dict payload, but a config can also carry a token directly
    in its auth block (e.g. round-tripped from a previously-saved config).
    """
    if not token and config.auth:
        if config.auth.type == "bearer" and config.auth.token:
            return config.auth.token
        if config.auth.type == "oauth2" and config.auth.client_secret:
            return config.auth.client_secret
    return token


def _collect_rest_preview(
    config: RestSourceConfig, limit: int, token: Optional[str] = None
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    resolved_token = _resolve_preview_token(config, token)
    try:
        _, raw_pages, error = run_preview(config, token=resolved_token, limit=limit)
        return raw_pages, error
    except Exception as exc:
        # Defensive: run_preview itself only surfaces fetch failures via its
        # `error` return value; this guards against anything else going
        # wrong before/around that (e.g. codegen failing).
        return [], str(exc)


def _collect_records(
    config: RestSourceConfig, token: str | None, limit: int
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Collect preview records (via the generated fetch code) and their dtypes."""

    resolved_token = _resolve_preview_token(config, token)
    records, _, _ = run_preview(config, token=resolved_token, limit=limit)

    if not records:
        return records, []

    spark = _get_or_create_spark()
    try:
        df = _get_preview_df(
            records=records, schema_ddl=config.stream.schema, spark=spark
        )
        dtypes = df.dtypes
        sample_row = records[0]
        dtype_dicts: List[Dict[str, str]] = [
            {"column": column, "type": str(dtype)}
            for column, dtype in dtypes
            if column in sample_row
        ]
        return records, dtype_dicts
    finally:
        spark.stop()


def _get_preview_df(
    *,
    records: List[Dict[str, Any]],
    schema_ddl: Optional[str],
    spark: "SparkSession",
):
    """Build a Spark DataFrame from already-fetched preview records.

    Used only to infer/validate column dtypes for the builder UI; the
    records themselves are already known (fetched by `run_preview`), so no
    additional network access happens here.
    """
    if schema_ddl:
        return spark.createDataFrame(records, schema=schema_ddl)
    return spark.createDataFrame(records)


def _get_or_create_spark() -> Any:
    """Get or create a Spark session."""
    from pyspark.sql import SparkSession

    spark = (
        SparkSession.builder.appName("polymo-builder")
        .config("spark.sql.adaptive.enabled", "false")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "false")
        .getOrCreate()
    )
    return spark
