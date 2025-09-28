"""FastAPI application powering the polymo web builder."""

from __future__ import annotations

from functools import partial
from importlib import resources
from typing import Any, Dict, List, Optional, Tuple

import yaml
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from ..config import (
    ConfigError,
    RestSourceConfig,
    StreamConfig,
    config_to_dict,
    dump_config,
    parse_config,
)

PACKAGE_ROOT = resources.files(__package__)
TEMPLATES = Jinja2Templates(directory=str(PACKAGE_ROOT.joinpath("templates")))
STATIC_PATH = PACKAGE_ROOT.joinpath("static")

SAMPLE_CONFIG = """\
version: 0.1
source:
  type: rest
  base_url: https://jsonplaceholder.typicode.com
stream:
  name: posts
  path: /posts
  params:
    _limit: 25
  pagination:
    type: none
  incremental:
    mode: null
    cursor_param: null
    cursor_field: null
  infer_schema: true
  schema: null
"""

SAMPLE_CONFIG_OBJECT = parse_config(yaml.safe_load(SAMPLE_CONFIG))
SAMPLE_CONFIG_DICT = config_to_dict(SAMPLE_CONFIG_OBJECT)
SAMPLE_CONFIG_YAML = dump_config(SAMPLE_CONFIG_OBJECT)


class ValidationRequest(BaseModel):
    config: Optional[str] = Field(None, description="YAML configuration text")
    config_dict: Optional[Dict[str, Any]] = Field(
        None, description="Configuration provided as a dictionary"
    )

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _ensure_payload(self) -> "ValidationRequest":
        if self.config is None and self.config_dict is None:
            raise ValueError("Either 'config' or 'config_dict' must be provided")
        return self


class ValidationResponse(BaseModel):
    valid: bool
    stream: str | None = None
    message: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    yaml: Optional[str] = None


class SampleRequest(BaseModel):
    config: Optional[str] = None
    config_dict: Optional[Dict[str, Any]] = None
    stream: Optional[str] = None
    limit: int = Field(20, ge=1, le=500, description="Maximum records to preview")

    model_config = ConfigDict(extra="ignore")

    @model_validator(mode="after")
    def _ensure_payload(self) -> "SampleRequest":
        if self.config is None and self.config_dict is None:
            raise ValueError("Either 'config' or 'config_dict' must be provided")
        return self


class SampleResponse(BaseModel):
    stream: str
    records: List[Dict[str, Any]]
    dtypes: List[Dict[str, str]] = Field(default_factory=list, description="Spark column data types")


class FormatRequest(BaseModel):
    config_dict: Dict[str, Any]


class FormatResponse(BaseModel):
    yaml: str


def create_app() -> FastAPI:
    app = FastAPI(title="polymo builder", version="0.1.0")

    app.mount("/static", StaticFiles(directory=str(STATIC_PATH)), name="static")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> FileResponse:  # pragma: no cover - static convenience endpoint
        return FileResponse(STATIC_PATH / "favicon.ico")

    @app.get("/apple-touch-icon.png", include_in_schema=False)
    @app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
    async def apple_touch_icon() -> FileResponse:  # pragma: no cover - static convenience endpoint
        # Re-use existing high-res logo as apple touch icon
        return FileResponse(STATIC_PATH / "logo192.png")

    @app.get("/")
    async def index(request: Request) -> Any:
        return TEMPLATES.TemplateResponse(
            "index.html",
            {
                "request": request,
                "sample_config": SAMPLE_CONFIG_YAML,
                "sample_config_dict": SAMPLE_CONFIG_DICT,
            },
        )

    @app.post("/api/validate", response_model=ValidationResponse)
    async def validate_config(payload: ValidationRequest) -> ValidationResponse:
        try:
            config = _load_config_payload(payload.config, payload.config_dict)
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
            yaml=dump_config(config),
        )

    @app.post("/api/sample", response_model=SampleResponse)
    async def sample_records(payload: SampleRequest) -> SampleResponse:
        try:
            config = _load_config_payload(payload.config, payload.config_dict)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        stream_config = config.stream
        if payload.stream and payload.stream != stream_config.name:
            raise HTTPException(
                status_code=404,
                detail=f"Stream '{payload.stream}' not found in configuration",
            )

        try:
            records, dtypes = await run_in_threadpool(
                partial(_collect_records, config, stream_config, payload.limit)
            )
        except Exception as exc:  # pragma: no cover - surfaced to UI
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        return SampleResponse(stream=stream_config.name, records=records, dtypes=dtypes)

    @app.post("/api/format", response_model=FormatResponse)
    async def format_config(payload: FormatRequest) -> FormatResponse:
        try:
            config = parse_config(payload.config_dict)
        except ConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return FormatResponse(yaml=dump_config(config))

    return app


def _load_config_payload(
    config_text: Optional[str], config_dict: Optional[Dict[str, Any]]
) -> RestSourceConfig:
    if config_dict is not None:
        return parse_config(config_dict)
    if config_text is None:
        raise ConfigError("Configuration payload is missing")
    return _parse_yaml(config_text)


def _parse_yaml(text: str) -> RestSourceConfig:
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML: {exc}") from exc
    return parse_config(parsed)


def _collect_records(config: RestSourceConfig, stream: StreamConfig, limit: int) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]]]:
    """Collect processed records and dtypes using PySpark DataSource."""
    import tempfile
    import os
    from ..config import dump_config

    # Create a temporary config file for Spark to use
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
        config_yaml = dump_config(config)
        f.write(config_yaml)
        config_path = f.name

    spark = _get_or_create_spark()
    try:
        df = _get_preview_df(config_path, stream, spark)
        records = df.limit(limit).collect()
        dtypes = df.dtypes
        record_dicts = [row.asDict(recursive=True) for row in records]
        dtype_dicts = [{"column": dtype[0], "type": str(dtype[1])} for dtype in dtypes if dtype[0] in record_dicts[0]]
        return record_dicts, dtype_dicts
    finally:
        spark.stop()
        os.unlink(config_path)

def _get_preview_df(config_path: str, stream: StreamConfig, spark: "SparkSession"):
    """Get a Spark DataFrame for previewing data from the specified stream."""

    from polymo import ApiReader

    _get_or_create_spark()
    spark.dataSource.register(ApiReader)

    # Alternative approach: Use the DataSource directly without format registration
    # Create the DataSource instance manually
    options = {
        "config_path": config_path,
        "stream": stream,
    }
    return spark.read.format("polymo").options(**options).load()

def _get_or_create_spark() -> Any:
    """Get or create a Spark session."""
    from pyspark.sql import SparkSession

    spark = SparkSession.builder \
        .appName("polymo-builder") \
        .config("spark.sql.adaptive.enabled", "false") \
        .config("spark.sql.adaptive.coalescePartitions.enabled", "false") \
        .getOrCreate()
    return spark
