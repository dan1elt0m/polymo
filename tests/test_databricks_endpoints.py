from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, List, Optional

import pytest

fastapi = pytest.importorskip("fastapi", reason="FastAPI is required for builder tests")
from fastapi.testclient import TestClient  # noqa: E402

from polymo.builder import app as builder_app  # noqa: E402
from polymo.builder import create_app, databricks  # noqa: E402
from polymo.builder.databricks import (  # noqa: E402
    DatabricksCliError,
    list_profiles,
    run_cli,
    run_cli_text,
)
from polymo.codegen import generate_core  # noqa: E402
from polymo.config import parse_config  # noqa: E402

SAMPLE_CONFIG_DICT = {
    "version": "0.1",
    "source": {"type": "rest", "base_url": "https://example.com"},
    "stream": {"name": "posts", "path": "/posts"},
}


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


def make_text_runner(
    *,
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
    capture: Optional[List[Any]] = None,
):
    def runner(argv, *, timeout, cwd=None):
        if capture is not None:
            capture.append({"argv": argv, "cwd": cwd, "timeout": timeout})
        return FakeCompleted(returncode=returncode, stdout=stdout, stderr=stderr)

    return runner


def install_fake_text_runner(monkeypatch, **kwargs):
    """Patch the default runner used by run_cli_text via deploy/run endpoints."""
    capture: List[Any] = []
    kwargs.setdefault("capture", capture)
    fake = make_text_runner(**kwargs)
    monkeypatch.setattr(databricks, "_run_subprocess", fake)
    return capture


def write_bundle_project(base: Path, *, pipeline_key: str = "demo_pipeline") -> Path:
    """Write the minimal files `_require_bundle_project` looks for."""
    base.mkdir(parents=True, exist_ok=True)
    (base / "databricks.yml").write_text("bundle:\n  name: demo\n")
    (base / ".polymo-bundle.json").write_text(
        json.dumps(
            {
                "pipeline_key": pipeline_key,
                "stream": "posts",
                "generated_by": "polymo 0.0.0",
            }
        )
    )
    return base


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


def test_run_cli_malformed_json_raises_databricks_cli_error():
    runner = make_runner(returncode=0, stdout="{not valid json")

    with pytest.raises(DatabricksCliError) as exc_info:
        run_cli(["catalogs", "list"], profile=None, runner=runner)

    assert "invalid json" in str(exc_info.value).lower()
    assert "not valid json" in str(exc_info.value)


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


def test_cli_malformed_json_returns_502(monkeypatch):
    install_fake_runner(monkeypatch, returncode=0, stdout="{not valid json")

    app = create_app()
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/databricks/catalogs")

    assert response.status_code == 502
    assert "invalid json" in response.json()["detail"].lower()
    assert "not valid json" in response.json()["detail"]


# ---------------------------------------------------------------------------
# run_cli_text unit tests
# ---------------------------------------------------------------------------


def test_run_cli_text_happy_path_no_json_flag_and_cwd_passed(tmp_path):
    captured = []
    runner = make_text_runner(stdout="Deploying...\nDone!", capture=captured)

    result = run_cli_text(
        ["bundle", "deploy", "-t", "dev"], profile=None, cwd=tmp_path, runner=runner
    )

    assert result == "Deploying...\nDone!"
    call = captured[0]
    assert call["argv"] == ["databricks", "bundle", "deploy", "-t", "dev"]
    assert "-o" not in call["argv"]
    assert "json" not in call["argv"]
    assert call["cwd"] == tmp_path


def test_run_cli_text_places_profile_flag(tmp_path):
    captured = []
    runner = make_text_runner(stdout="ok", capture=captured)

    run_cli_text(
        ["bundle", "run", "my_pipeline", "-t", "dev"],
        profile="my-profile",
        cwd=tmp_path,
        runner=runner,
    )

    argv = captured[0]["argv"]
    assert argv == [
        "databricks",
        "bundle",
        "run",
        "my_pipeline",
        "-t",
        "dev",
        "--profile",
        "my-profile",
    ]


def test_run_cli_text_nonzero_exit_raises_with_combined_output(tmp_path):
    runner = make_text_runner(
        returncode=1, stdout="partial progress", stderr="deploy failed: bad config"
    )

    with pytest.raises(DatabricksCliError) as exc_info:
        run_cli_text(["bundle", "deploy", "-t", "dev"], cwd=tmp_path, runner=runner)

    assert "partial progress" in exc_info.value.stderr
    assert "deploy failed: bad config" in exc_info.value.stderr


def test_run_cli_text_timeout_raises_databricks_cli_error(tmp_path):
    def runner(argv, *, timeout, cwd=None):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    with pytest.raises(DatabricksCliError) as exc_info:
        run_cli_text(["bundle", "deploy", "-t", "dev"], cwd=tmp_path, runner=runner)

    assert "timed out" in str(exc_info.value).lower()


def test_run_cli_text_missing_executable_raises_file_not_found(tmp_path):
    def runner(argv, *, timeout, cwd=None):
        raise FileNotFoundError("no such file")

    with pytest.raises(FileNotFoundError):
        run_cli_text(["bundle", "deploy", "-t", "dev"], cwd=tmp_path, runner=runner)


def test_run_cli_text_strips_ansi_and_caps_output(tmp_path):
    ansi_prefix = "\x1b[31m"
    long_stdout = ansi_prefix + ("x" * 9000) + "END"
    runner = make_text_runner(stdout=long_stdout)

    result = run_cli_text(
        ["bundle", "deploy", "-t", "dev"], cwd=tmp_path, runner=runner
    )

    assert "\x1b" not in result
    assert len(result) <= 8000
    assert result.endswith("END")


# ---------------------------------------------------------------------------
# /api/databricks/bootstrap
# ---------------------------------------------------------------------------


def test_bootstrap_writes_expected_files(tmp_path):
    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/api/databricks/bootstrap",
        json={
            "config_dict": SAMPLE_CONFIG_DICT,
            "project_dir": str(tmp_path),
            "project_name": "demo",
            "catalog": "main",
            "schema": "raw",
        },
    )

    assert response.status_code == 200
    payload = response.json()

    project_path = Path(payload["project_path"])
    assert project_path == tmp_path / "demo"
    assert set(payload["files"]) == {
        "databricks.yml",
        "src/demo/__init__.py",
        "src/demo/client.py",
        "src/demo/source.py",
        "pipelines/posts.py",
        "README.md",
        ".polymo-bundle.json",
    }

    for relpath in payload["files"]:
        assert (project_path / relpath).is_file()

    manifest = json.loads((project_path / ".polymo-bundle.json").read_text())
    assert manifest["pipeline_key"] == "demo_pipeline"
    assert manifest["stream"] == "posts"

    config = parse_config(SAMPLE_CONFIG_DICT)
    assert (project_path / "src/demo/client.py").read_text() == generate_core(config)


def test_bootstrap_refuses_nonempty_dir_without_overwrite(tmp_path):
    target = tmp_path / "demo"
    target.mkdir()
    (target / "stray.txt").write_text("leftover")

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/bootstrap",
        json={
            "config_dict": SAMPLE_CONFIG_DICT,
            "project_dir": str(tmp_path),
            "project_name": "demo",
            "catalog": "main",
            "schema": "raw",
        },
    )

    assert response.status_code == 400
    assert "already exists" in response.json()["detail"]
    # untouched
    assert (target / "stray.txt").read_text() == "leftover"


def test_bootstrap_overwrite_true_succeeds_over_nonempty_dir(tmp_path):
    target = tmp_path / "demo"
    target.mkdir()
    (target / "stray.txt").write_text("leftover")

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/bootstrap",
        json={
            "config_dict": SAMPLE_CONFIG_DICT,
            "project_dir": str(tmp_path),
            "project_name": "demo",
            "catalog": "main",
            "schema": "raw",
            "overwrite": True,
        },
    )

    assert response.status_code == 200
    assert (target / "databricks.yml").is_file()
    # bootstrap doesn't wipe the directory, just writes its own files over it
    assert (target / "stray.txt").read_text() == "leftover"


def test_bootstrap_rejects_home_directory(tmp_path, monkeypatch):
    fake_home = tmp_path / "homedir"
    fake_home.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/bootstrap",
        json={
            "config_dict": SAMPLE_CONFIG_DICT,
            "project_dir": str(tmp_path),
            "project_name": "homedir",
            "catalog": "main",
            "schema": "raw",
        },
    )

    assert response.status_code == 400
    assert "refusing" in response.json()["detail"].lower()


def test_bootstrap_rejects_path_inside_polymo_package_dir(tmp_path, monkeypatch):
    fake_package_dir = tmp_path / "site-packages" / "polymo"
    fake_package_dir.mkdir(parents=True)
    monkeypatch.setattr(builder_app, "_polymo_package_dir", lambda: fake_package_dir)

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/bootstrap",
        json={
            "config_dict": SAMPLE_CONFIG_DICT,
            "project_dir": str(fake_package_dir),
            "project_name": "demo",
            "catalog": "main",
            "schema": "raw",
        },
    )

    assert response.status_code == 400
    assert "polymo package directory" in response.json()["detail"]


def test_bootstrap_invalid_config_returns_400(tmp_path):
    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/bootstrap",
        json={
            "config_dict": {"version": "0.1"},  # missing required source/stream
            "project_dir": str(tmp_path),
            "project_name": "demo",
            "catalog": "main",
            "schema": "raw",
        },
    )

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# /api/databricks/deploy
# ---------------------------------------------------------------------------


def test_deploy_endpoint_happy_path(monkeypatch, tmp_path):
    project = write_bundle_project(tmp_path / "demo")
    capture = install_fake_text_runner(monkeypatch, stdout="Deployment complete!")

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/deploy",
        json={"project_path": str(project), "profile": "dev", "target": "dev"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"ok": True, "output": "Deployment complete!"}

    call = capture[0]
    assert call["argv"] == [
        "databricks",
        "bundle",
        "deploy",
        "-t",
        "dev",
        "--profile",
        "dev",
    ]
    assert Path(call["cwd"]) == project


def test_deploy_endpoint_not_a_bundle_project_returns_400(tmp_path):
    empty_dir = tmp_path / "not-a-bundle"
    empty_dir.mkdir()

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/deploy",
        json={"project_path": str(empty_dir)},
    )

    assert response.status_code == 400
    assert "not a polymo bundle project" in response.json()["detail"]


def test_deploy_endpoint_nonzero_exit_returns_ok_false_with_output(
    monkeypatch, tmp_path
):
    project = write_bundle_project(tmp_path / "demo")
    install_fake_text_runner(
        monkeypatch, returncode=1, stderr="Error: permission denied"
    )

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/deploy",
        json={"project_path": str(project)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "permission denied" in payload["output"]


def test_deploy_endpoint_cli_missing_returns_501(monkeypatch, tmp_path):
    project = write_bundle_project(tmp_path / "demo")

    def runner(argv, *, timeout, cwd=None):
        raise FileNotFoundError("no such file")

    monkeypatch.setattr(databricks, "_run_subprocess", runner)

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/deploy",
        json={"project_path": str(project)},
    )

    assert response.status_code == 501


def test_deploy_endpoint_timeout_returns_ok_false(monkeypatch, tmp_path):
    project = write_bundle_project(tmp_path / "demo")

    def runner(argv, *, timeout, cwd=None):
        raise subprocess.TimeoutExpired(cmd=argv, timeout=timeout)

    monkeypatch.setattr(databricks, "_run_subprocess", runner)

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/deploy",
        json={"project_path": str(project)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "timed out" in payload["output"].lower()


# ---------------------------------------------------------------------------
# /api/databricks/run
# ---------------------------------------------------------------------------


def test_run_endpoint_uses_pipeline_key_from_manifest(monkeypatch, tmp_path):
    project = write_bundle_project(tmp_path / "demo", pipeline_key="my_custom_pipeline")
    capture = install_fake_text_runner(monkeypatch, stdout="Update completed.")

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/run",
        json={"project_path": str(project), "target": "dev"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload == {"ok": True, "output": "Update completed."}

    argv = capture[0]["argv"]
    assert argv == [
        "databricks",
        "bundle",
        "run",
        "my_custom_pipeline",
        "-t",
        "dev",
    ]


def test_run_endpoint_not_a_bundle_project_returns_400(tmp_path):
    empty_dir = tmp_path / "not-a-bundle"
    empty_dir.mkdir()

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/run",
        json={"project_path": str(empty_dir)},
    )

    assert response.status_code == 400


def test_run_endpoint_missing_pipeline_key_returns_400(tmp_path):
    project = tmp_path / "demo"
    project.mkdir()
    (project / "databricks.yml").write_text("bundle:\n  name: demo\n")
    (project / ".polymo-bundle.json").write_text(json.dumps({"stream": "posts"}))

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/run",
        json={"project_path": str(project)},
    )

    assert response.status_code == 400
    assert "pipeline_key" in response.json()["detail"]


def test_run_endpoint_nonzero_exit_returns_ok_false(monkeypatch, tmp_path):
    project = write_bundle_project(tmp_path / "demo")
    install_fake_text_runner(monkeypatch, returncode=1, stderr="pipeline not found")

    app = create_app()
    client = TestClient(app)
    response = client.post(
        "/api/databricks/run",
        json={"project_path": str(project)},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is False
    assert "pipeline not found" in payload["output"]
