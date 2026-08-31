"""Thin wrapper around the `databricks` CLI for read-only builder endpoints.

The builder shells out to the user's locally-installed `databricks` CLI
(which reads `~/.databrickscfg`) rather than talking to the Databricks REST
API directly. Every call here is read-only and stateless: the builder never
stores Databricks credentials or state of its own.
"""

from __future__ import annotations

import configparser
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Callable, List, Optional, Sequence

CLI_NOT_FOUND_DETAIL = (
    "databricks CLI not found — install: https://docs.databricks.com/dev-tools/cli"
)

DATABRICKS_CFG_PATH = Path.home() / ".databrickscfg"

_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
_STDERR_TAIL_CHARS = 800
_DEFAULT_TIMEOUT = 30.0

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class DatabricksCliError(Exception):
    """Raised when the `databricks` CLI exits non-zero or times out.

    `stderr` carries a short, ANSI-stripped tail of the CLI's stderr output
    (safe to surface to the UI: argv passed to the CLI never contains
    secrets, only profile/catalog/scope names).
    """

    def __init__(self, message: str, *, stderr: str = "") -> None:
        super().__init__(message)
        self.stderr = stderr


def _strip_ansi(text: str) -> str:
    return _ANSI_ESCAPE_RE.sub("", text)


def _stderr_tail(stderr: str) -> str:
    cleaned = _strip_ansi(stderr).strip()
    if len(cleaned) > _STDERR_TAIL_CHARS:
        return cleaned[-_STDERR_TAIL_CHARS:]
    return cleaned


def _run_subprocess(
    argv: Sequence[str], *, timeout: float
) -> "subprocess.CompletedProcess[str]":
    """Default runner: the real `databricks` CLI via subprocess.

    Kept as a plain module-level function (rather than bound as a default
    parameter value) so tests can monkeypatch it in place and have that
    take effect for callers that don't pass their own `runner`.
    """
    return subprocess.run(
        list(argv), capture_output=True, text=True, timeout=timeout, check=False
    )


def run_cli(
    args: List[str],
    *,
    profile: Optional[str] = None,
    timeout: float = _DEFAULT_TIMEOUT,
    runner: Optional[Runner] = None,
) -> Any:
    """Run `databricks <args...> [--profile <profile>] -o json` and parse stdout.

    Args:
        args: CLI subcommand + positional arguments, e.g. ``["catalogs", "list"]``.
        profile: `~/.databrickscfg` profile name; omitted flag falls back to
            the CLI's own default-profile resolution.
        timeout: seconds before the subprocess is killed.
        runner: injectable subprocess runner for tests; defaults to the
            module-level `_run_subprocess` (looked up at call time, so
            monkeypatching it works even when `runner` isn't passed).

    Returns:
        The parsed JSON stdout, or `[]` if stdout was empty/whitespace.

    Raises:
        FileNotFoundError: the `databricks` executable isn't on PATH.
        DatabricksCliError: the CLI exited non-zero or timed out.
    """
    active_runner = runner or _run_subprocess

    argv: List[str] = ["databricks", *args]
    if profile:
        argv += ["--profile", profile]
    argv += ["-o", "json"]

    try:
        result = active_runner(argv, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise DatabricksCliError(
            f"databricks CLI timed out after {timeout:.0f}s"
        ) from exc
    # FileNotFoundError intentionally propagates uncaught: callers (the
    # endpoint layer) translate it into a distinct "install the CLI" error.

    if result.returncode != 0:
        raise DatabricksCliError(
            f"databricks CLI exited with status {result.returncode}",
            stderr=_stderr_tail(result.stderr or ""),
        )

    stdout = (result.stdout or "").strip()
    if not stdout:
        return []
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise DatabricksCliError(
            f"databricks CLI returned invalid JSON: {stdout[:200]!r}"
        ) from exc


def list_profiles(path: Optional[Path] = None) -> List[str]:
    """Return `~/.databrickscfg` profile names (section headers).

    "DEFAULT" is included only when it explicitly sets a `host` (a bare
    DEFAULT section with no host isn't a usable profile). Missing config
    file -> `[]`.
    """
    cfg_path = path if path is not None else DATABRICKS_CFG_PATH
    if not cfg_path.exists():
        return []

    parser = configparser.ConfigParser()
    try:
        parser.read(cfg_path)
    except configparser.Error:
        return []

    profiles: List[str] = []
    if parser.defaults().get("host"):
        profiles.append("DEFAULT")
    profiles.extend(parser.sections())
    return profiles


def extract_names(
    data: Any, *, wrapper_keys: Sequence[str], item_key: str
) -> List[str]:
    """Defensively pull a list of name/key strings out of CLI JSON output.

    Handles both known CLI output shapes: a bare JSON array of objects, or
    an object wrapping the array under one of `wrapper_keys` (e.g.
    `{"scopes": [...]}`). Tolerates `None`, empty input, and items that
    aren't dicts (plain strings) or that are missing `item_key`.
    """
    if data is None:
        return []

    if isinstance(data, dict):
        for key in wrapper_keys:
            value = data.get(key)
            if isinstance(value, list):
                data = value
                break
        else:
            return []

    if not isinstance(data, list):
        return []

    names: List[str] = []
    for item in data:
        if isinstance(item, dict):
            value = item.get(item_key)
        else:
            value = item
        if value:
            names.append(str(value))
    return names
