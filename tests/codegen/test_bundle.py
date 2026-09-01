from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from polymo.codegen import generate_bundle, generate_core
from polymo.config import (
    IncrementalConfig,
    PaginationConfig,
    PartitionConfig,
)
from tests.codegen.helpers import assert_hygiene, make_config

GOLDEN_DIR = Path(__file__).parent / "golden_bundle"

EXPECTED_KEYS = {
    "databricks.yml",
    "src/demo/__init__.py",
    "src/demo/client.py",
    "pipelines/posts.py",
    "README.md",
    ".polymo-bundle.json",
}


def _bundle(config, **overrides):
    kwargs = dict(project_name="demo", catalog="main", schema="raw")
    kwargs.update(overrides)
    return generate_bundle(config, **kwargs)


def test_file_set_keys():
    config = make_config(base_url="https://x")
    files = _bundle(config)
    assert set(files) == EXPECTED_KEYS


def test_pkg_and_stream_names_are_sanitized_identifiers():
    config = make_config(base_url="https://x", name="my posts!")
    files = generate_bundle(
        config, project_name="my project!", catalog="main", schema="raw"
    )
    assert set(files) == {
        "databricks.yml",
        "src/my_project_/__init__.py",
        "src/my_project_/client.py",
        "pipelines/my_posts_.py",
        "README.md",
        ".polymo-bundle.json",
    }


# --- client.py byte-equality -------------------------------------------------
# The single source of truth constraint: src/<pkg>/client.py must be
# EXACTLY generate_core(config), so preview/export/bundle can never drift.

CLIENT_EQUALITY_CASES = {
    "plain": make_config(base_url="https://x"),
    "windowed_incremental": make_config(
        base_url="https://x",
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
        schema="id INT, updated STRING",
    ),
    "streaming": make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    ),
    "xml": make_config(
        base_url="https://x",
        response_format="xml",
        xml_record_path=".//item",
    ),
}


@pytest.mark.parametrize("case", CLIENT_EQUALITY_CASES)
def test_client_byte_equals_generate_core(case):
    config = CLIENT_EQUALITY_CASES[case]
    files = _bundle(config)
    assert files["src/demo/client.py"] == generate_core(config)


# --- pipeline file hygiene + import correctness ------------------------------

PIPELINE_IMPORT_CASES = {
    "plain": (CLIENT_EQUALITY_CASES["plain"], ["fetch_records", "_infer_schema"]),
    "windowed_incremental": (
        CLIENT_EQUALITY_CASES["windowed_incremental"],
        ["fetch_records", "WINDOWS", "_write_state"],
    ),
    "streaming": (CLIENT_EQUALITY_CASES["streaming"], ["fetch_page"]),
    "xml": (CLIENT_EQUALITY_CASES["xml"], ["fetch_records", "_infer_schema"]),
    "explicit_schema": (
        make_config(base_url="https://x", schema="id BIGINT, name STRING"),
        ["fetch_records"],
    ),
}


@pytest.mark.parametrize("case", PIPELINE_IMPORT_CASES)
def test_pipeline_file_hygiene_and_imports(case):
    config, expected_names = PIPELINE_IMPORT_CASES[case]
    files = _bundle(config)
    pipeline = files["pipelines/posts.py"]

    ast.parse(pipeline)
    assert_hygiene(pipeline)

    import_line = next(
        line
        for line in pipeline.splitlines()
        if line.startswith("from demo.client import")
    )
    imported = [name.strip() for name in import_line.split("import", 1)[1].split(",")]
    # the last name shares its line with a trailing lint-suppression comment
    imported[-1] = imported[-1].split("#")[0].strip()
    assert imported == expected_names

    # every imported name must actually be referenced in the body (no
    # unused imports slipping past hygiene by coincidence of ruff config)
    body = pipeline.split(import_line, 1)[1]
    for name in expected_names:
        assert name in body, f"{name} imported but never used in {case}"

    # no accidental same-module assumption: the pipeline file never
    # defines fetch_records/_infer_schema/etc. itself, only imports them
    for name in expected_names:
        assert f"def {name}(" not in pipeline


def test_streaming_pipeline_does_not_import_fetch_records():
    config = CLIENT_EQUALITY_CASES["streaming"]
    files = _bundle(config)
    pipeline = files["pipelines/posts.py"]
    import_line = next(
        line
        for line in pipeline.splitlines()
        if line.startswith("from demo.client import")
    )
    assert "fetch_records" not in import_line
    assert "WINDOWS" not in import_line
    assert "_infer_schema" not in import_line
    assert "_write_state" not in import_line


# --- executor pickle simulation ----------------------------------------------
# The critical regression this fix closes: a bundle-deployed pipeline is
# pickled by Spark on the driver and unpickled on an *executor* that never
# ran `databricks.yml`'s root_path sys.path extension (that only applies to
# the driver process). Without `cloudpickle.register_pickle_by_value`, the
# executor's unpickle fails with `ModuleNotFoundError: No module named
# '<pkg>'` because the DataSource/reader reference the client module's
# functions BY REFERENCE, not by value.
#
# This is simulated with two real subprocesses sharing nothing but a pickle
# file on disk: subprocess A has the generated `src/<pkg>/client.py` on its
# sys.path (like the driver) and performs exactly the import + registration
# dance the generated pipeline file performs, then pickles `fetch_records`.
# Subprocess B has NOTHING of `<pkg>` on its sys.path (like an executor) and
# just unpickles + calls the function against a real mock HTTP server. A
# negative-control run (pickled without the registration) proves the test
# actually exercises the failure mode this fix prevents, not just a tautology.

_BUILD_PICKLE_SCRIPT = """
import importlib
import sys

pkg, src_root, register, out_path = sys.argv[1], sys.argv[2], sys.argv[3] == "1", sys.argv[4]
sys.path.insert(0, src_root)

from pyspark import cloudpickle

client_module = importlib.import_module(f"{pkg}.client")
fetch_records = client_module.fetch_records

if register:
    cloudpickle.register_pickle_by_value(client_module)

with open(out_path, "wb") as fh:
    fh.write(cloudpickle.dumps(fetch_records))
"""

_LOAD_AND_CALL_SCRIPT = """
import json
import sys

from pyspark import cloudpickle

with open(sys.argv[1], "rb") as fh:
    fetch_records = cloudpickle.loads(fh.read())

sys.stdout.write(json.dumps(list(fetch_records())))
"""


def test_executor_can_unpickle_client_functions_without_pkg_on_its_path(
    tmp_path, http_server
):
    http_server.routes["/posts"] = lambda query, headers, body: (
        200,
        [{"id": 1, "title": "hello from the executor"}],
        {},
    )
    config = make_config(base_url=http_server.url, name="posts", path="/posts")

    pkg = "execsim_pkg"
    src_root = tmp_path / "driver_sys_path" / "src"
    pkg_dir = src_root / pkg
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "client.py").write_text(generate_core(config))

    build_script = tmp_path / "build_pickle.py"
    build_script.write_text(_BUILD_PICKLE_SCRIPT)
    load_script = tmp_path / "load_and_call.py"
    load_script.write_text(_LOAD_AND_CALL_SCRIPT)

    # Executor working directory: deliberately NOT src_root, and nothing
    # about `pkg` is importable from here (unlike the driver, which got
    # root_path added to its sys.path by databricks.yml).
    executor_cwd = tmp_path / "executor_cwd"
    executor_cwd.mkdir()

    def build(register: str, out_name: str) -> Path:
        out_path = tmp_path / out_name
        result = subprocess.run(
            [
                sys.executable,
                str(build_script),
                pkg,
                str(src_root),
                register,
                str(out_path),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return out_path

    def load_on_executor(pickle_path: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(load_script), str(pickle_path)],
            capture_output=True,
            text=True,
            cwd=str(executor_cwd),
        )

    # --- positive: registered by value, exactly like the generated pipeline file
    registered_pickle = build("1", "payload_registered.pkl")
    result = load_on_executor(registered_pickle)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == [{"id": 1, "title": "hello from the executor"}]

    # --- negative control: same flow, minus the registration line this fix
    # adds. Proves the executor really does need it — without this, the
    # positive result above wouldn't demonstrate anything.
    unregistered_pickle = build("0", "payload_unregistered.pkl")
    failure = load_on_executor(unregistered_pickle)
    assert failure.returncode != 0
    assert "ModuleNotFoundError" in failure.stderr
    assert pkg in failure.stderr


# --- databricks.yml -----------------------------------------------------------


def test_databricks_yml_parses_with_expected_resource_keys():
    config = make_config(base_url="https://x")
    files = _bundle(config, project_name="demo", catalog="main", schema="raw")
    data = yaml.safe_load(files["databricks.yml"])

    assert data["bundle"]["name"] == "demo"

    pipelines = data["resources"]["pipelines"]
    assert set(pipelines) == {"demo_pipeline"}
    pipeline = pipelines["demo_pipeline"]
    assert pipeline["catalog"] == "main"
    assert pipeline["schema"] == "raw"
    assert pipeline["root_path"] == "src"
    assert pipeline["libraries"] == [{"glob": {"include": "pipelines/posts.py"}}]

    targets = data["targets"]
    assert targets["dev"]["mode"] == "development"
    assert targets["dev"]["default"] is True
    assert targets["prod"]["mode"] == "production"


def test_databricks_yml_quotes_values_with_special_characters():
    config = make_config(base_url="https://x")
    files = generate_bundle(
        config, project_name="demo: bundle", catalog="main", schema="raw"
    )
    # must still be valid YAML even though project_name contains a colon
    data = yaml.safe_load(files["databricks.yml"])
    assert data["bundle"]["name"]  # sanitized identifier, non-empty


# --- manifest -----------------------------------------------------------------


def test_manifest_has_expected_keys():
    config = make_config(base_url="https://x")
    files = _bundle(config)
    manifest = json.loads(files[".polymo-bundle.json"])
    assert manifest["pipeline_key"] == "demo_pipeline"
    assert manifest["stream"] == "posts"
    assert manifest["generated_by"].startswith("polymo ")


# --- README ---------------------------------------------------------------


def test_readme_mentions_deploy_and_table_location():
    config = make_config(base_url="https://x")
    files = _bundle(config)
    readme = files["README.md"]
    assert "databricks bundle deploy -t dev" in readme
    assert "main.raw" in readme
    lines = readme.splitlines()
    assert len(lines) <= 20


# --- validation parity with generate() ----------------------------------------


def test_streaming_without_schema_rejected_same_as_generate():
    config = make_config(base_url="https://x", streaming=True)
    with pytest.raises(Exception):
        _bundle(config)


# --- golden bundle dir ----------------------------------------------------


def _golden_config():
    return make_config(
        base_url="https://jsonplaceholder.typicode.com",
        name="posts",
        path="/posts",
        params={"_limit": 20},
    )


def test_golden_bundle():
    config = _golden_config()
    files = generate_bundle(
        config, project_name="jsonplaceholder-demo", catalog="main", schema="raw"
    )
    seeded = []
    for relpath, content in files.items():
        golden_path = GOLDEN_DIR / relpath
        if not golden_path.exists():
            golden_path.parent.mkdir(parents=True, exist_ok=True)
            golden_path.write_text(content)
            seeded.append(str(golden_path))
    if seeded:
        pytest.skip(f"golden bundle seeded: {seeded}")

    for relpath, content in files.items():
        golden_path = GOLDEN_DIR / relpath
        if relpath == ".polymo-bundle.json":
            # generated_by carries the installed polymo version, which
            # legitimately drifts across releases; compare structurally
            # instead of byte-for-byte so a version bump alone doesn't
            # break this fixture.
            got = json.loads(content)
            want = json.loads(golden_path.read_text())
            assert got["pipeline_key"] == want["pipeline_key"]
            assert got["stream"] == want["stream"]
            assert got["generated_by"].startswith("polymo ")
            continue
        assert content == golden_path.read_text(), (
            f"generated {relpath} changed; if intended, delete {golden_path} and rerun"
        )
    golden_files = {
        str(p.relative_to(GOLDEN_DIR)) for p in GOLDEN_DIR.rglob("*") if p.is_file()
    }
    assert golden_files == set(files)
