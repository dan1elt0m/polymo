from __future__ import annotations

import subprocess
from typing import Any, List, Optional

import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI is required for builder tests")
from fastapi.testclient import TestClient  # noqa: E402

from polymo.builder import create_app, databricks  # noqa: E402
from polymo.builder.databricks import DatabricksCliError, list_profiles, run_cli  # noqa: E402


class FakeCompleted:
    def __init__(self, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def make_runner(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    capture: Optional[List[Any]] = None,
):
    def runner(argv, *, timeout):
        if capture is not None:
            capture.append(argv)
        return FakeCompleted(returncode=returncode, stdout=stdout, stderr=stderr)

    return runner


def install_fake_runner(monkeypatch, **kwargs):
    """Patch the module-level default runner used by run_cli via app endpoints."""
    capture: List[Any] = []
    kwargs.setdefault("capture", capture)
    fake = make_runner(**kwargs)
    monkeypatch.setattr(databricks, "_run_subprocess", fake)
    return capture


# ---------------------------------------------------------------------------
# run_cli unit tests
# ---------------------------------------------------------------------------


def test_run_cli_happy_path_parses_json_array():
    captured = []
    runner = make_runner(stdout='[{"name": "main"}]', capture=captured)

    result = run_cli(["catalogs", "list"], profile=None, runner=runner)

    assert result == [{"name": "main"}]
    argv = captured[0]
    assert argv[0] == "databricks"
    assert argv[1:3] == ["catalogs", "list"]
    assert argv[-2:] == ["-o", "json"]
    assert "--profile" not in argv


def test_run_cli_places_profile_flag():
    captured = []
    runner = make_runner(stdout="[]", capture=captured)

    run_cli(["catalogs", "list"], profile="my-profile", runner=runner)

    argv = captured[0]
    assert "--profile" in argv
    idx = argv.index("--profile")
    assert argv[idx + 1] == "my-profile"


def test_run_cli_empty_stdout_returns_empty_list():
    runner = make_runner(stdout="   ")

    result = run_cli(["secrets", "list-scopes"], profile=None, runner=runner)

    assert result == []


def test_run_cli_nonzero_exit_raises_with_stderr_detail():
    runner = make_runner(returncode=1, stderr="boom: something failed")

    with pytest.raises(DatabricksCliError) as exc_info:
        run_cli(["catalogs", "list"], profile=None, runner=runner)

    assert "boom: something failed" in exc_info.value.stderr


def test_run_cli_stderr_tail_is_truncated_and_ansi_stripped():
    ansi_prefix = "\x1b[31m"
    long_stderr = ansi_prefix + ("x" * 2000) + "END"
    runner = make_runner(returncode=1, stderr=long_stderr)

    with pytest.raises(DatabricksCliError) as exc_info:
        run_cli(["catalogs", "list"], profile=None, runner=runner)

    assert "\x1b" not in exc_info.value.stderr
    assert len(exc_info.value.stderr) <= 800
    assert exc_info.value.stderr.endswith("END")


def test_run_cli_timeout_raises_databricks_cli_error():
    def runner(argv, *, timeout):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    with pytest.raises(DatabricksCliError) as exc_info:
        run_cli(["catalogs", "list"], profile=None, runner=runner)

    assert "timed out" in str(exc_info.value).lower()


def test_run_cli_missing_executable_raises_file_not_found():
    def runner(argv, *, timeout):
        raise FileNotFoundError("no such file")

    with pytest.raises(FileNotFoundError):
        run_cli(["catalogs", "list"], profile=None, runner=runner)


# ---------------------------------------------------------------------------
# list_profiles unit tests
# ---------------------------------------------------------------------------


def test_list_profiles_missing_file_returns_empty(tmp_path):
    missing = tmp_path / "does-not-exist"

    assert list_profiles(path=missing) == []


def test_list_profiles_parses_sections_and_default(tmp_path):
    cfg = tmp_path / ".databrickscfg"
    cfg.write_text(
        "[DEFAULT]\n"
        "host = https://default.example.com\n"
        "token = abc\n"
        "\n"
        "[staging]\n"
        "host = https://staging.example.com\n"
        "token = def\n"
    )

    profiles = list_profiles(path=cfg)

    assert "DEFAULT" in profiles
    assert "staging" in profiles


def test_list_profiles_excludes_default_without_host(tmp_path):
    cfg = tmp_path / ".databrickscfg"
    cfg.write_text("[staging]\nhost = https://staging.example.com\ntoken = def\n")

    profiles = list_profiles(path=cfg)

    assert "DEFAULT" not in profiles
    assert profiles == ["staging"]


# ---------------------------------------------------------------------------
# Endpoint tests
# ---------------------------------------------------------------------------


def test_profiles_endpoint_reads_databrickscfg(monkeypatch, tmp_path):
    cfg = tmp_path / ".databrickscfg"
    cfg.write_text("[dev]\nhost = https://dev.example.com\ntoken = x\n")
    monkeypatch.setattr(databricks, "DATABRICKS_CFG_PATH", cfg)

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/profiles")

    assert response.status_code == 200
    assert response.json() == {"profiles": ["dev"]}


def test_catalogs_endpoint_happy_path(monkeypatch):
    capture = install_fake_runner(
        monkeypatch, stdout='[{"name": "main"}, {"name": "samples"}]'
    )

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/catalogs", params={"profile": "dev"})

    assert response.status_code == 200
    assert response.json() == {"catalogs": ["main", "samples"]}
    argv = capture[0]
    assert argv[1:3] == ["catalogs", "list"]
    assert "--profile" in argv and argv[argv.index("--profile") + 1] == "dev"
    assert argv[-2:] == ["-o", "json"]


def test_catalogs_endpoint_without_profile(monkeypatch):
    capture = install_fake_runner(monkeypatch, stdout="[]")

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/catalogs")

    assert response.status_code == 200
    assert response.json() == {"catalogs": []}
    assert "--profile" not in capture[0]


def test_schemas_endpoint_happy_path(monkeypatch):
    capture = install_fake_runner(
        monkeypatch, stdout='[{"name": "default"}, {"name": "bronze"}]'
    )

    app = create_app()
    client = TestClient(app)
    response = client.get(
        "/api/databricks/schemas", params={"profile": "dev", "catalog": "main"}
    )

    assert response.status_code == 200
    assert response.json() == {"schemas": ["default", "bronze"]}
    argv = capture[0]
    assert argv[1:4] == ["schemas", "list", "main"]


def test_schemas_endpoint_requires_catalog_param(monkeypatch):
    install_fake_runner(monkeypatch, stdout="[]")

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/schemas", params={"profile": "dev"})

    assert response.status_code == 422


def test_secret_scopes_endpoint_happy_path(monkeypatch):
    capture = install_fake_runner(
        monkeypatch,
        stdout='{"scopes": [{"name": "kv-scope", "backend_type": "AZURE_KEYVAULT"}, {"name": "local"}]}',
    )

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/secret-scopes", params={"profile": "dev"})

    assert response.status_code == 200
    assert response.json() == {"secret_scopes": ["kv-scope", "local"]}
    argv = capture[0]
    assert argv[1:3] == ["secrets", "list-scopes"]


def test_secret_scopes_endpoint_handles_bare_array(monkeypatch):
    install_fake_runner(monkeypatch, stdout='[{"name": "scope-a"}]')

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/secret-scopes")

    assert response.status_code == 200
    assert response.json() == {"secret_scopes": ["scope-a"]}


def test_secret_keys_endpoint_happy_path(monkeypatch):
    capture = install_fake_runner(
        monkeypatch,
        stdout='{"secrets": [{"key": "api-token", "last_updated_timestamp": "1"}]}',
    )

    app = create_app()
    client = TestClient(app)
    response = client.get(
        "/api/databricks/secret-keys", params={"profile": "dev", "scope": "kv-scope"}
    )

    assert response.status_code == 200
    assert response.json() == {"secret_keys": ["api-token"]}
    argv = capture[0]
    assert argv[1:4] == ["secrets", "list-secrets", "kv-scope"]


def test_secret_keys_endpoint_requires_scope_param(monkeypatch):
    install_fake_runner(monkeypatch, stdout="[]")

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/secret-keys", params={"profile": "dev"})

    assert response.status_code == 422


def test_cli_missing_returns_501(monkeypatch):
    def runner(argv, *, timeout):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(databricks, "_run_subprocess", runner)

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/catalogs")

    assert response.status_code == 501
    assert "databricks CLI not found" in response.json()["detail"]


def test_cli_error_returns_502_with_stderr_detail(monkeypatch):
    install_fake_runner(
        monkeypatch, returncode=1, stderr="permission denied: not authenticated"
    )

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/catalogs")

    assert response.status_code == 502
    assert "permission denied" in response.json()["detail"]


def test_cli_timeout_returns_502(monkeypatch):
    def runner(argv, *, timeout):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(databricks, "_run_subprocess", runner)

    app = create_app()
    client = TestClient(app)
    response = client.get("/api/databricks/catalogs")

    assert response.status_code == 502
    assert "timed out" in response.json()["detail"].lower()
