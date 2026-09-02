"""Render a Databricks Asset Bundle project from a REST source config.

The project layout mirrors `databricks bundle init default-python`: a
`databricks.yml` with one Lakeflow Declarative Pipeline resource declaring a
`whl` artifact (built via `uv build --wheel` at deploy time), a root
`pyproject.toml` that packages `src/<pkg>` as that wheel, the generated
fetch/schema code under `src/<pkg>/client.py`, the connector's
`DataSource`/reader under `src/<pkg>/source.py`, and a thin pipeline source
under `pipelines/` that imports both and wires the `@dp.table`. Zero polymo
imports appear anywhere in the output — `src/<pkg>/client.py` is exactly
`generate_core(config)` for a config with no auth secret refs, the same
code the builder's preview/export use, so a bundle project can never drift
from what those show *when there's nothing secret to resolve differently*.
When a secret ref IS present, `client.py` intentionally diverges: see
`generator._context`'s docstring for why (short version: `src/<pkg>` ships
as a wheel, so Spark's Python workers re-import it fresh with no
SparkSession/dbutils available — a module-level `_dbx_secret(...)`/
`_uc_secret(...)` call would blow up there). The pipeline resource's
`environment.dependencies` installs the built wheel, so `src/<pkg>` is
importable on the driver AND every executor without any pickle-by-value
trick; any auth secret ref is instead resolved driver-side in
`pipelines/<stream>.py` and threaded through as DataSource reader options
(see that template).
"""

from __future__ import annotations

import json
import keyword
from importlib import metadata
from typing import Dict, List

from ..config import RestSourceConfig
from .generator import (
    _context,
    _ENV,
    _identifier,
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


def _pascal_case(pkg: str) -> str:
    """PascalCase a sanitized package identifier, for use as a class name.

    `pkg` is already a valid Python identifier (see `_identifier`), so this
    only needs to reassemble it: split on `_`, capitalize each piece
    (`maileon_contacts` -> `MaileonContacts`), join. Falls back to a
    generic name in the unlikely case the result isn't itself a valid,
    non-keyword identifier (e.g. `pkg` made entirely of underscores).
    """
    name = "".join(part[:1].upper() + part[1:] for part in pkg.split("_") if part)
    if not name or not name.isidentifier() or keyword.iskeyword(name):
        return "Generated"
    return name


def _bundle_import_names(ctx: Dict) -> List[str]:
    """Names the generated `source.py` needs from `<pkg>.client`.

    Mirrors exactly what `bundle/source.py.jinja` references from the core
    module for the given config shape (see the branches in that template):
    the streaming reader only ever calls `fetch_page`; every other variant
    calls `fetch_records`, plus `WINDOWS` when partitioned over static
    windows, `fetch_page`/`_probe_total_pages` when fanning out one
    partition per page, `_infer_schema` when no explicit schema was given,
    and the cursor helpers when tracking an incremental cursor
    (`_read_state` only when the driver resolves the cursor up front for
    the page fan-out).
    """
    if ctx["streaming"]:
        return ["fetch_page"]
    names = ["fetch_records"]
    if ctx["has_windows"]:
        names.append("WINDOWS")
    if ctx["page_partitions"]:
        names.extend(["fetch_page", "_probe_total_pages"])
    if not ctx["schema_ddl"]:
        names.append("_infer_schema")
    if ctx["incremental"]:
        if ctx["page_partitions"]:
            names.append("_read_state")
        names.extend(["_cursor_of", "_write_state"])
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
        pyproject.toml            # packages src/<pkg> as a wheel (uv_build)
        src/<pkg>/__init__.py
        src/<pkg>/client.py       # generate_core(config, for_bundle=True) —
                                   # identical to generate_core(config) unless
                                   # an auth secret ref is present
        src/<pkg>/source.py       # the <PascalCase(pkg)>Source DataSource + reader
        pipelines/<stream>.py     # imports both, wires the @dp.table
        README.md
        .polymo-bundle.json       # read back by the "Run on Databricks" flow
    """
    validate_dp_wiring(config)

    # for_bundle=True: any auth-secret-ref slot renders as the "REPLACE_ME"
    # placeholder here instead of a direct `_dbx_secret(...)`/`_uc_secret(...)`
    # call — see `generator._context`'s docstring. The helper function
    # definitions are unaffected (still gated on has_secret_refs/
    # has_uc_secret_refs); `bundle_secret_slots` (also in this context)
    # drives the driver-side resolution in pipeline.py.jinja instead.
    ctx = _context(config, for_bundle=True)
    pkg = _identifier(project_name)
    stream = ctx["func_name"]
    pipeline_key = f"{pkg}_pipeline"
    table_name = _identifier(ctx["stream_name"])
    source_class_name = f"{_pascal_case(pkg)}Source"

    core = _ENV.get_template("core.py.jinja").render(**ctx)

    bundle_ctx = dict(ctx)
    bundle_ctx["bundle_pkg"] = pkg
    bundle_ctx["bundle_imports"] = _bundle_import_names(ctx)
    bundle_ctx["source_class_name"] = source_class_name
    source_file = _ENV.get_template("bundle/source.py.jinja").render(**bundle_ctx)
    pipeline_file = _ENV.get_template("bundle/pipeline.py.jinja").render(**bundle_ctx)

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

    state_remote = ctx["incremental"] and ctx["state_remote"]
    pyproject_toml = _ENV.get_template("bundle/pyproject.toml.jinja").render(
        pkg=pkg,
        has_uc_secret_refs=ctx["has_uc_secret_refs"],
        state_remote=state_remote,
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
        state_remote=state_remote,
        state_path=ctx["state_path"],
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
        "pyproject.toml": pyproject_toml,
        f"src/{pkg}/__init__.py": "",
        f"src/{pkg}/client.py": core,
        f"src/{pkg}/source.py": source_file,
        f"pipelines/{stream}.py": pipeline_file,
        "README.md": readme,
        ".polymo-bundle.json": manifest,
    }
