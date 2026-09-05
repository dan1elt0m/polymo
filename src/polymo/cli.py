"""Command line entry points for polymo."""

from __future__ import annotations

import argparse
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="polymo", description="Launch the local Polymo UI"
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind (default: %(default)s)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind (default: %(default)s)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (useful during development)",
    )

    args = parser.parse_args(argv)

    if not _require_ui_deps():
        return 1

    import uvicorn

    uvicorn.run(
        "polymo.ui.app:create_app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        factory=True,
    )
    return 0


def _require_ui_deps() -> bool:
    """Verify the install is intact (pyspark present and compatible).

    polymo now depends on pyspark unconditionally, so a missing or
    incompatible pyspark means the install itself is broken. Returns True
    when the environment is ready to launch the UI. On a missing
    pyspark install, prints a friendly hint and returns False so the caller
    can exit cleanly instead of tracebacking.
    """
    try:
        import pyspark
    except ModuleNotFoundError:
        print(
            "polymo's dependencies are incomplete — reinstall with: "
            "pip install --force-reinstall polymo"
        )
        return False

    if not pyspark.__version__.startswith("4."):
        raise ImportError(
            "pyspark>=4.0.0 is required: reinstall with "
            "pip install --force-reinstall polymo"
        )

    return True


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
