"""FastAPI application powering the polymo web builder."""

from __future__ import annotations

from functools import partial
from importlib import metadata, resources
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field
from starlette.concurrency import run_in_threadpool

from ..codegen import CodegenError, generate
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

        raw_pages, rest_error = await run_in_threadpool(
            partial(_collect_rest_preview, config, payload.limit, payload.token)
        )

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

    return app


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
