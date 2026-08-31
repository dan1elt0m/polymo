"""Render a Databricks Asset Bundle project from a REST source config.

The project layout mirrors `databricks bundle init default-python`: a
`databricks.yml` with one Lakeflow Declarative Pipeline resource, the
generated fetch/schema code under `src/<pkg>/`, and a thin pipeline source
under `pipelines/` that imports from it. Zero polymo imports appear
anywhere in the output — `src/<pkg>/client.py` is exactly
`generate_core(config)`, the same code the builder's preview/export use, so
a bundle project can never drift from what those show.
"""

from __future__ import annotations

import json
from importlib import metadata
from typing import Dict, List

from ..config import RestSourceConfig
from .generator import (
    _context,
    _ENV,
    _identifier,
    generate_core,
    validate_dp_wiring,
)

__all__ = ["generate_bundle"]


def _polymo_version() -> str:
    try:
        return metadata.version("polymo")
    except metadata.PackageNotFoundError:
        return "0.0.0"


def _yaml_str(value: str) -> str:
    """Render `value` as a double-quoted YAML scalar (valid JSON is valid YAML)."""
    return json.dumps(value)


def _bundle_import_names(ctx: Dict) -> List[str]:
    """Names the standalone pipeline file needs from `<pkg>.client`.

    Mirrors exactly what `dp.py.jinja` references from the core module for
    the given config shape (see the branches in that template): the
    streaming reader only ever calls `fetch_page`; every other variant
    calls `fetch_records`, plus `WINDOWS` when partitioned, `_infer_schema`
    when no explicit schema was given, and `_write_state` when tracking an
    incremental cursor.
    """
    if ctx["streaming"]:
        return ["fetch_page"]
    names = ["fetch_records"]
    if ctx["has_windows"]:
        names.append("WINDOWS")
    if not ctx["schema_ddl"]:
        names.append("_infer_schema")
    if ctx["incremental_mode"]:
        names.append("_write_state")
    return names


def generate_bundle(
    config: RestSourceConfig,
    *,
    project_name: str,
    catalog: str,
    schema: str,
) -> Dict[str, str]:
    """Render a full Databricks Asset Bundle project for `config`.

    Returns a mapping of project-relative path to file content:

        databricks.yml
        src/<pkg>/__init__.py
        src/<pkg>/client.py       # == generate_core(config), byte-for-byte
        pipelines/<stream>.py     # imports from <pkg>.client
        README.md
        .polymo-bundle.json       # read back by the "Run on Databricks" flow
    """
    validate_dp_wiring(config)

    ctx = _context(config)
    pkg = _identifier(project_name)
    stream = ctx["func_name"]
    pipeline_key = f"{pkg}_pipeline"
    table_name = _identifier(ctx["stream_name"])

    core = generate_core(config)

    pipeline_ctx = dict(ctx)
    pipeline_ctx["bundle_pkg"] = pkg
    pipeline_ctx["bundle_imports"] = _bundle_import_names(ctx)
    pipeline_file = _ENV.get_template("bundle/pipeline.py.jinja").render(**pipeline_ctx)

    databricks_yml = _ENV.get_template("bundle/databricks.yml.jinja").render(
        project_name=project_name,
        bundle_pkg=pkg,
        bundle_name_repr=_yaml_str(pkg),
        pipeline_key=pipeline_key,
        pipeline_key_repr=_yaml_str(pipeline_key),
        catalog_repr=_yaml_str(catalog),
        schema_repr=_yaml_str(schema),
        stream=stream,
    )

    readme = _ENV.get_template("bundle/readme.md.jinja").render(
        project_name=project_name,
        pkg=pkg,
        stream=stream,
        stream_name=ctx["stream_name"],
        pipeline_key=pipeline_key,
        catalog=catalog,
        schema=schema,
        table_name=table_name,
    )

    manifest = (
        json.dumps(
            {
                "pipeline_key": pipeline_key,
                "stream": stream,
                "generated_by": f"polymo {_polymo_version()}",
            },
            indent=2,
        )
        + "\n"
    )

    return {
        "databricks.yml": databricks_yml,
        f"src/{pkg}/__init__.py": "",
        f"src/{pkg}/client.py": core,
        f"pipelines/{stream}.py": pipeline_file,
        "README.md": readme,
        ".polymo-bundle.json": manifest,
    }
