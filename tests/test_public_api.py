"""Tombstone tests for the public API as polymo sheds its runtime surface.

This file grew incrementally across the Phase 3 tasks (see
docs/superpowers/plans/2026-08-28-codegen-phase3.md): Task 2 removed the
Spark custom data source, Task 3 removed RestClient, Task 4 removed the YAML
+ pydantic config API. Task 4 also asserts the final `__all__`.
"""

import pytest


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
