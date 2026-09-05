"""Opt-in gate for the live public-API suite.

Everything under `tests/live/` talks to real third-party APIs over the
network and runs the generated scripts through a real local SparkSession,
so it is skipped unless `POLYMO_LIVE=1` is set (see
`.github/workflows/live.yml` for the scheduled run).
"""

from __future__ import annotations

import os

import pytest


def pytest_collection_modifyitems(config, items):
    if os.environ.get("POLYMO_LIVE"):
        return
    skip = pytest.mark.skip(
        reason="live public-API test; set POLYMO_LIVE=1 to run tests/live"
    )
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)
