from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from polymo.codegen import generate_bundle, generate_core
from polymo.codegen.bundle import _pascal_case
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
    "src/demo/source.py",
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
        "src/my_project_/source.py",
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


# --- source.py hygiene + import correctness -----------------------------------
# The DataSource/reader classes live in src/<pkg>/source.py (not the
# pipeline file) and reach the fetch/schema helpers via a relative import
# from .client.

SOURCE_IMPORT_CASES = {
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


@pytest.mark.parametrize("case", SOURCE_IMPORT_CASES)
def test_source_file_hygiene_and_imports(case):
    config, expected_names = SOURCE_IMPORT_CASES[case]
    files = _bundle(config)
    source = files["src/demo/source.py"]

    ast.parse(source)
    assert_hygiene(source)

    import_line = next(
        line for line in source.splitlines() if line.startswith("from .client import")
    )
    imported = [name.strip() for name in import_line.split("import", 1)[1].split(",")]
    # the last name shares its line with a trailing lint-suppression comment
    imported[-1] = imported[-1].split("#")[0].strip()
    assert imported == expected_names

    # every imported name must actually be referenced in the body (no
    # unused imports slipping past hygiene by coincidence of ruff config)
    body = source.split(import_line, 1)[1]
    for name in expected_names:
        assert name in body, f"{name} imported but never used in {case}"

    # no accidental same-module assumption: source.py never defines
    # fetch_records/_infer_schema/etc. itself, only imports them
    for name in expected_names:
        assert f"def {name}(" not in source

    # the pipeline file, in turn, never imports these directly — only the
    # client/source module objects (see test_pipeline_file_registers_*)
    pipeline = files["pipelines/posts.py"]
    assert "from demo.client import" not in pipeline
    assert "from demo import client" in pipeline


def test_streaming_source_does_not_import_fetch_records():
    config = CLIENT_EQUALITY_CASES["streaming"]
    files = _bundle(config)
    source = files["src/demo/source.py"]
    import_line = next(
        line for line in source.splitlines() if line.startswith("from .client import")
    )
    assert "fetch_records" not in import_line
    assert "WINDOWS" not in import_line
    assert "_infer_schema" not in import_line
    assert "_write_state" not in import_line


# --- pipeline file: registers client + source by value, thin @dp.table wiring -

PIPELINE_CASES = {
    "plain": CLIENT_EQUALITY_CASES["plain"],
    "windowed_incremental": CLIENT_EQUALITY_CASES["windowed_incremental"],
    "streaming": CLIENT_EQUALITY_CASES["streaming"],
    "xml": CLIENT_EQUALITY_CASES["xml"],
}


@pytest.mark.parametrize("case", PIPELINE_CASES)
def test_pipeline_file_registers_client_and_source_by_value(case):
    config = PIPELINE_CASES[case]
    files = _bundle(config)
    pipeline = files["pipelines/posts.py"]

    ast.parse(pipeline)
    assert_hygiene(pipeline)

    assert "from demo import client as _client_module" in pipeline
    assert "from demo import source as _source_module" in pipeline
    assert "from pyspark import cloudpickle" in pipeline
    assert "cloudpickle.register_pickle_by_value(_client_module)" in pipeline
    assert "cloudpickle.register_pickle_by_value(_source_module)" in pipeline
    assert "spark.dataSource.register(_source_module.DemoSource)" in pipeline

    # the pipeline file itself never defines the DataSource/reader classes
    # (they live in source.py) and never calls the fetch/schema helpers
    # directly (only via the registered modules)
    assert "class DemoSource" not in pipeline
    assert "class _Reader" not in pipeline
    assert "fetch_records(" not in pipeline
    assert "fetch_page(" not in pipeline


# --- connector-named DataSource class -----------------------------------------


@pytest.mark.parametrize(
    ("pkg", "expected"),
    [
        ("demo", "DemoSource"),
        ("maileon_contacts", "MaileonContactsSource"),
        ("jsonplaceholder_demo", "JsonplaceholderDemoSource"),
        ("my_project_", "MyProjectSource"),
        ("t_123", "T123Source"),
    ],
)
def test_pascal_case_class_name(pkg, expected):
    assert f"{_pascal_case(pkg)}Source" == expected


def test_datasource_class_named_after_connector():
    config = make_config(base_url="https://x", name="my posts!")
    files = generate_bundle(
        config, project_name="maileon contacts", catalog="main", schema="raw"
    )
    source = files["src/maileon_contacts/source.py"]
    pipeline = files["pipelines/my_posts_.py"]

    assert "class MaileonContactsSource(DataSource):" in source
    assert "spark.dataSource.register(_source_module.MaileonContactsSource)" in pipeline
    # generic name is gone entirely, not just renamed in one spot
    assert "RestSource" not in source
    assert "RestSource" not in pipeline


def test_streaming_datasource_class_also_named_after_connector():
    config = CLIENT_EQUALITY_CASES["streaming"]
    files = _bundle(config)
    source = files["src/demo/source.py"]
    pipeline = files["pipelines/posts.py"]

    assert "class DemoSource(DataSource):" in source
    assert "spark.dataSource.register(_source_module.DemoSource)" in pipeline
    assert "RestStreamSource" not in source
    assert "RestStreamSource" not in pipeline


# --- executor pickle simulation ----------------------------------------------
# The critical regression this fix closes: a bundle-deployed pipeline is
# pickled by Spark on the driver and unpickled on an *executor* that never
# ran `databricks.yml`'s root_path sys.path extension (that only applies to
# the driver process). Without `cloudpickle.register_pickle_by_value`, the
# executor's unpickle fails with `ModuleNotFoundError: No module named
# '<pkg>'` because the DataSource/reader (now living in `<pkg>.source`, which
# itself imports from `<pkg>.client`) reference those functions BY
# REFERENCE, not by value — so *both* modules need registering, not just
# `client`.
#
# This is simulated with two real subprocesses sharing nothing but pickle
# files on disk: subprocess A has the generated `src/<pkg>/{client,source}.py`
# on its sys.path (like the driver) and performs exactly the import +
# registration dance the generated pipeline file performs (parameterized by
# `mode`, so the test can register neither/only-client/both), then pickles
# both `client.fetch_records` and `source._Reader` (the reader class).
# Subprocess B has NOTHING of `<pkg>` on its sys.path (like an executor) and
# separately unpickles + calls each artifact against a real mock HTTP
# server — instantiating `_Reader` with a stub schema object and calling
# `.read()`, exactly like Spark would after `<pkg>.source.<Class>.reader()`
# hands one back. Negative-control runs prove the test actually exercises
# the failure mode this fix prevents, not just a tautology:
#   - mode="none":         both pickles fail to load (nothing registered)
#   - mode="client_only":  fetch_records loads fine, but the reader class
#                          still fails — proving `source` must be
#                          registered too, not just `client`
#   - mode="both":         both load and run correctly

_BUILD_PICKLES_SCRIPT = """
import importlib
import sys

pkg, src_root, mode, out_dir = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4]
sys.path.insert(0, src_root)

from pyspark import cloudpickle

client_module = importlib.import_module(f"{pkg}.client")
source_module = importlib.import_module(f"{pkg}.source")

if mode in ("both", "client_only"):
    cloudpickle.register_pickle_by_value(client_module)
if mode == "both":
    cloudpickle.register_pickle_by_value(source_module)

with open(f"{out_dir}/fetch_records.pkl", "wb") as fh:
    fh.write(cloudpickle.dumps(client_module.fetch_records))

with open(f"{out_dir}/reader_cls.pkl", "wb") as fh:
    fh.write(cloudpickle.dumps(source_module._Reader))
"""

_LOAD_FETCH_SCRIPT = """
import json
import sys

from pyspark import cloudpickle

with open(sys.argv[1], "rb") as fh:
    fetch_records = cloudpickle.loads(fh.read())

sys.stdout.write(json.dumps(list(fetch_records())))
"""

_LOAD_READER_SCRIPT = """
import json
import sys

from pyspark import cloudpickle


class _Field:
    def __init__(self, name):
        self.name = name


class _Schema:
    def __init__(self, names):
        self.fields = [_Field(name) for name in names]


with open(sys.argv[1], "rb") as fh:
    reader_cls = cloudpickle.loads(fh.read())

reader = reader_cls(_Schema(["id", "title"]))
sys.stdout.write(json.dumps(list(reader.read(None))))
"""


def test_executor_can_unpickle_client_and_source_without_pkg_on_its_path(
    tmp_path, http_server
):
    http_server.routes["/posts"] = lambda query, headers, body: (
        200,
        [{"id": 1, "title": "hello from the executor"}],
        {},
    )
    config = make_config(base_url=http_server.url, name="posts", path="/posts")

    pkg = "execsim_pkg"
    files = generate_bundle(config, project_name=pkg, catalog="main", schema="raw")
    src_root = tmp_path / "driver_sys_path" / "src"
    pkg_dir = src_root / pkg
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text("")
    (pkg_dir / "client.py").write_text(files[f"src/{pkg}/client.py"])
    (pkg_dir / "source.py").write_text(files[f"src/{pkg}/source.py"])

    build_script = tmp_path / "build_pickles.py"
    build_script.write_text(_BUILD_PICKLES_SCRIPT)
    load_fetch_script = tmp_path / "load_fetch.py"
    load_fetch_script.write_text(_LOAD_FETCH_SCRIPT)
    load_reader_script = tmp_path / "load_reader.py"
    load_reader_script.write_text(_LOAD_READER_SCRIPT)

    # Executor working directory: deliberately NOT src_root, and nothing
    # about `pkg` is importable from here (unlike the driver, which got
    # root_path added to its sys.path by databricks.yml).
    executor_cwd = tmp_path / "executor_cwd"
    executor_cwd.mkdir()

    def build(mode: str) -> Path:
        out_dir = tmp_path / f"pickles_{mode}"
        out_dir.mkdir()
        result = subprocess.run(
            [sys.executable, str(build_script), pkg, str(src_root), mode, str(out_dir)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        return out_dir

    def load_fetch(out_dir: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(load_fetch_script),
                str(out_dir / "fetch_records.pkl"),
            ],
            capture_output=True,
            text=True,
            cwd=str(executor_cwd),
        )

    def load_reader(out_dir: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(load_reader_script), str(out_dir / "reader_cls.pkl")],
            capture_output=True,
            text=True,
            cwd=str(executor_cwd),
        )

    # --- positive: both client and source registered by value, exactly like
    # the generated pipeline file does
    both = build("both")

    fetch_result = load_fetch(both)
    assert fetch_result.returncode == 0, fetch_result.stderr
    assert json.loads(fetch_result.stdout) == [
        {"id": 1, "title": "hello from the executor"}
    ]

    reader_result = load_reader(both)
    assert reader_result.returncode == 0, reader_result.stderr
    assert json.loads(reader_result.stdout) == [[1, "hello from the executor"]]

    # --- negative control 1: nothing registered — both artifacts fail on
    # the executor with the exact ModuleNotFoundError this fix prevents.
    none = build("none")

    fetch_failure = load_fetch(none)
    assert fetch_failure.returncode != 0
    assert "ModuleNotFoundError" in fetch_failure.stderr
    assert pkg in fetch_failure.stderr

    reader_failure = load_reader(none)
    assert reader_failure.returncode != 0
    assert "ModuleNotFoundError" in reader_failure.stderr
    assert pkg in reader_failure.stderr

    # --- negative control 2: only `client` registered — proves registering
    # `client` alone (as the pre-restructure fix did) is NOT sufficient now
    # that the reader class lives in `source`; `source` must be registered
    # independently even though it only imports from `client`, never the
    # other way around.
    client_only = build("client_only")

    fetch_ok = load_fetch(client_only)
    assert fetch_ok.returncode == 0, fetch_ok.stderr
    assert json.loads(fetch_ok.stdout) == [
        {"id": 1, "title": "hello from the executor"}
    ]

    reader_still_fails = load_reader(client_only)
    assert reader_still_fails.returncode != 0
    assert "ModuleNotFoundError" in reader_still_fails.stderr
    assert pkg in reader_still_fails.stderr


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
