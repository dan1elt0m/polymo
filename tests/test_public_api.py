"""Tombstone tests for the public API as polymo sheds its runtime surface.

This file grows incrementally across the Phase 3 tasks (see
docs/superpowers/plans/2026-08-28-codegen-phase3.md): Task 2 removes the
Spark custom data source, Task 3 removes RestClient, Task 4 removes the YAML
+ pydantic config API. Only the assertions for symbols/modules already
deleted belong here; do not assert the final `__all__` until Task 4.
"""

import pytest


def test_removed_runtime_symbols_are_gone():
    import polymo

    assert not hasattr(polymo, "ApiReader")
    assert hasattr(polymo, "CodegenError")


def test_runtime_modules_deleted():
    with pytest.raises(ModuleNotFoundError):
        import polymo.datasource  # noqa: F401
