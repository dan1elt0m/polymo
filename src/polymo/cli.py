"""Command line entry points for polymo."""

from __future__ import annotations

import argparse
from typing import Sequence


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="polymo", description="Utilities for the polymo toolkit"
    )
    subparsers = parser.add_subparsers(dest="command")
    bld_parser = subparsers.add_parser("builder", help="Launch the local builder UI")
    bld_parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind (default: %(default)s)"
    )
    bld_parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind (default: %(default)s)"
    )
    bld_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (useful during development)",
    )

    args = parser.parse_args(argv)

    # Check Spark Version
    import pyspark

    if not pyspark.__version__.startswith("4."):
        raise ImportError(
            "pyspark>=4.0.0 is required: run pip install 'polymo[builder]'"
        )

    if args.command == "builder":
        import uvicorn

        uvicorn.run(
            "polymo.builder.app:create_app",
            host=args.host,
            port=args.port,
            reload=args.reload,
            factory=True,
        )
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
