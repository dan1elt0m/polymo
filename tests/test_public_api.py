"""Tombstone tests for the public API as polymo sheds its runtime surface.

This file grew incrementally across the Phase 3 tasks (see
docs/superpowers/plans/2026-08-28-codegen-phase3.md): Task 2 removed the
Spark custom data source, Task 3 removed RestClient, Task 4 removed the YAML
+ pydantic config API. Task 4 also asserts the final `__all__`.
"""

import subprocess
import sys
import textwrap

import pytest


def test_import_polymo_does_not_eagerly_load_pyspark():
    """`pip install polymo` depends on pyspark, but `import polymo` must not
    eagerly load it — pyspark's import is slow and codegen-only use (calling
    `generate()` / `parse_config()` without the Builder) shouldn't pay for it
    at startup.

    `import polymo` pulls in codegen, which pulls in config — config.py must
    not import pyspark at module load time. Runs in a subprocess so
    sys.modules starts clean regardless of what earlier tests in this
    process already imported.
    """
    code = (
        "import polymo\n"
        "assert polymo.generate\n"
        "assert not any(m.split('.')[0] == 'pyspark' for m in __import__('sys').modules), "
        "'pyspark imported eagerly'\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_generate_with_schema_ddl_does_not_load_pyspark():
    """generate() for a config with a `schema` DDL string must stay pyspark-free.

    Schema DDL is validated at config-parse time (see `_validate_ddl` in
    polymo/config.py) and stays a plain string through codegen — it must
    never require pyspark, since codegen-only use (no Builder) shouldn't pay
    for importing pyspark even though it's an unconditional dependency.
    """
    code = textwrap.dedent(
        """
        import sys

        import polymo

        config = polymo.parse_config(
            {
                "version": 0.1,
                "source": {"type": "rest", "base_url": "https://api.test"},
                "stream": {"path": "/objects", "schema": "id BIGINT"},
            }
        )
        polymo.generate(config)
        assert not any(m.split(".")[0] == "pyspark" for m in sys.modules), (
            "pyspark imported while generating a config with a schema DDL"
        )
        """
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr


def test_removed_runtime_symbols_are_gone():
    import polymo

    assert not hasattr(polymo, "ApiReader")
    assert hasattr(polymo, "CodegenError")


def test_runtime_modules_deleted():
    with pytest.raises(ModuleNotFoundError):
        import polymo.datasource  # noqa: F401

    with pytest.raises(ModuleNotFoundError):
        import polymo.rest_client  # noqa: F401


def test_pydantic_config_module_deleted():
    with pytest.raises(ModuleNotFoundError):
        import polymo.pydantic_config  # noqa: F401


def test_yaml_config_symbols_are_gone():
    import polymo

    assert not hasattr(polymo, "load_config")
    assert not hasattr(polymo, "dump_config")
    assert not hasattr(polymo, "PolymoConfig")


def test_public_api_surface():
    import polymo

    assert polymo.__all__ == [
        "generate",
        "CodegenError",
        "RestSourceConfig",
        "config_to_dict",
        "parse_config",
    ]
