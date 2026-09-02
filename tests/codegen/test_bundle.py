from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
import yaml

from polymo.codegen import generate_bundle, generate_core
from polymo.codegen.bundle import _pascal_case
from polymo.config import (
    AuthConfig,
    IncrementalConfig,
    PaginationConfig,
    PartitionConfig,
    SecretRef,
)
from tests.codegen.helpers import assert_hygiene, make_config

GOLDEN_DIR = Path(__file__).parent / "golden_bundle"

EXPECTED_KEYS = {
    "databricks.yml",
    "pyproject.toml",
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
        "pyproject.toml",
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


def test_client_diverges_from_generate_core_when_secret_ref_present():
    """The byte-equality invariant above only holds when there's nothing
    secret-ref-shaped to render differently — see `generator._context`'s
    docstring for why. A bundle's `client.py` keeps a secret-ref slot typed
    `str | None = None` (never a direct `_dbx_secret(...)` call, and never
    the harmless-looking `"REPLACE_ME"` either — that would ship the
    literal string to the real API instead of failing loudly), on purpose:
    `src/<pkg>` ships as a wheel, so a module-level secret call there would
    run on a session-less Spark worker. This is a static-content regression
    test for that divergence; the executor simulation
    (`test_bundle_wheel_secret_ref_resolved_driver_side_and_shipped_via_options`)
    proves the driver-side replacement actually works end to end.
    """
    from polymo.codegen.generator import _context, _ENV

    config = make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="bearer", secret=SecretRef(scope="my-scope", key="my-key")
        ),
    )
    files = _bundle(config)
    bundle_client = files["src/demo/client.py"]
    standalone_core = generate_core(config)

    assert bundle_client != standalone_core
    assert "API_TOKEN: str | None = None" in bundle_client
    assert '_dbx_secret("my-scope", "my-key")' in standalone_core
    assert '_dbx_secret("my-scope", "my-key")' not in bundle_client
    # the helper function itself is still emitted in both — only the
    # module-level call site differs
    assert "def _dbx_secret(" in bundle_client
    assert "def _dbx_secret(" in standalone_core

    # bundle.py's actual rendering is exactly generate_core(config, for_bundle=True)
    for_bundle_core = _ENV.get_template("core.py.jinja").render(
        **_context(config, for_bundle=True)
    )
    assert bundle_client == for_bundle_core


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

    # the pipeline file, in turn, never imports the client helpers at all —
    # only the DataSource class from source.py (see
    # test_pipeline_file_imports_source_class_directly)
    pipeline = files["pipelines/posts.py"]
    assert "from demo.client import" not in pipeline
    assert "from demo import client" not in pipeline


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


# --- pipeline file: plain wheel-backed imports, thin @dp.table wiring --------

PIPELINE_CASES = {
    "plain": CLIENT_EQUALITY_CASES["plain"],
    "windowed_incremental": CLIENT_EQUALITY_CASES["windowed_incremental"],
    "streaming": CLIENT_EQUALITY_CASES["streaming"],
    "xml": CLIENT_EQUALITY_CASES["xml"],
}


@pytest.mark.parametrize("case", PIPELINE_CASES)
def test_pipeline_file_imports_source_class_directly(case):
    config = PIPELINE_CASES[case]
    files = _bundle(config)
    pipeline = files["pipelines/posts.py"]

    ast.parse(pipeline)
    assert_hygiene(pipeline)

    # No cloudpickle registration dance: databricks.yml builds src/demo into
    # a wheel and installs it via the pipeline's environment.dependencies,
    # so demo.source is importable directly, everywhere (driver + executors).
    assert "from demo.source import DemoSource" in pipeline
    assert "cloudpickle" not in pipeline
    assert "register_pickle_by_value" not in pipeline
    assert "_client_module" not in pipeline
    assert "_source_module" not in pipeline
    assert "spark.dataSource.register(DemoSource)" in pipeline

    # the pipeline file itself never defines the DataSource/reader classes
    # (they live in source.py) and never calls the fetch/schema helpers
    # directly (never imports from .client at all)
    assert "class DemoSource" not in pipeline
    assert "class _Reader" not in pipeline
    assert "fetch_records(" not in pipeline
    assert "fetch_page(" not in pipeline
    assert "from demo.client import" not in pipeline
    assert "from demo import client" not in pipeline


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
    assert "from maileon_contacts.source import MaileonContactsSource" in pipeline
    assert "spark.dataSource.register(MaileonContactsSource)" in pipeline
    # generic name is gone entirely, not just renamed in one spot
    assert "RestSource" not in source
    assert "RestSource" not in pipeline


def test_streaming_datasource_class_also_named_after_connector():
    config = CLIENT_EQUALITY_CASES["streaming"]
    files = _bundle(config)
    source = files["src/demo/source.py"]
    pipeline = files["pipelines/posts.py"]

    assert "class DemoSource(DataSource):" in source
    assert "from demo.source import DemoSource" in pipeline
    assert "spark.dataSource.register(DemoSource)" in pipeline
    assert "RestStreamSource" not in source
    assert "RestStreamSource" not in pipeline


# --- executor wheel simulation ------------------------------------------------
# The regression this fix closes: a bundle-deployed pipeline's
# DataSource/reader (living in `<pkg>.source`, which itself imports from
# `<pkg>.client`) must be importable on the driver AND on every *executor*.
# `databricks.yml`'s `root_path: src` only extends the driver's sys.path; the
# old fix shipped the code inside cloudpickle payloads instead. The new fix
# packages `src/<pkg>` as a wheel (`pyproject.toml` + `uv build --wheel`,
# exactly what `databricks.yml`'s `artifacts.default.build` runs at deploy
# time) and has the pipeline's `environment.dependencies` install it — so
# `<pkg>` is importable from the wheel alone, with nothing else on sys.path.
#
# This is simulated with two real subprocesses sharing nothing but the built
# wheel file on disk: subprocess A runs `uv build --wheel` against the
# generated `pyproject.toml` + `src/<pkg>/{__init__,client,source}.py`,
# exactly like `databricks bundle deploy` does. Subprocess B — with NOTHING
# on its sys.path except the built `.whl` file itself (wheels are directly
# zipimportable) — imports `<pkg>.client` + `<pkg>.source`, instantiates the
# generated DataSource class, and calls `fetch_records()` against a real
# mock HTTP server, exactly like Spark would after `<pkg>.source.<Class>()`.
# A negative control (no `.whl` on sys.path at all) proves the test actually
# exercises the failure mode this fix prevents, not just a tautology.

_LOAD_FROM_WHEEL_SCRIPT = """
import importlib
import json
import sys

whl_path, pkg, source_class_name = sys.argv[1], sys.argv[2], sys.argv[3]
if whl_path:
    sys.path.insert(0, whl_path)


class _Field:
    def __init__(self, name):
        self.name = name


class _Schema:
    def __init__(self, names):
        self.fields = [_Field(name) for name in names]


# Both imports below exercise the wheel end to end: `<pkg>.source` imports
# from `<pkg>.client` internally (a relative `from .client import ...`), so
# this also proves that intra-package import resolves from inside the
# wheel, not just the top-level package.
client_module = importlib.import_module(f"{pkg}.client")
source_module = importlib.import_module(f"{pkg}.source")

source_cls = getattr(source_module, source_class_name)
reader = source_cls(options={}).reader(_Schema(["id", "title"]))
# reader.read() calls client_module.fetch_records() internally, so this one
# call exercises both modules against the real mock HTTP server.
records = [dict(zip(["id", "title"], row)) for row in reader.read(None)]
sys.stdout.write(json.dumps(records))
"""


def _build_wheel(project_dir: Path) -> Path:
    """Run `uv build --wheel` in `project_dir`, returning the built .whl path.

    Mirrors exactly what `databricks bundle deploy` runs at deploy time
    (`artifacts.default.build` in `databricks.yml`) against the generated
    `pyproject.toml`.
    """
    uv = shutil.which("uv")
    if uv is None:  # pragma: no cover - exercised only when uv is missing
        pytest.skip("uv is not installed; required to build the bundle wheel")
    result = subprocess.run(
        [uv, "build", "--wheel"],
        cwd=str(project_dir),
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    dist_dir = project_dir / "dist"
    wheels = list(dist_dir.glob("*.whl"))
    assert len(wheels) == 1, f"expected exactly one wheel, got {wheels}"
    return wheels[0]


def test_bundle_wheel_installs_client_and_source_for_the_executor(
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
    source_class_name = f"{_pascal_case(pkg)}Source"

    project_dir = tmp_path / "bundle_project"
    (project_dir / "src" / pkg).mkdir(parents=True)
    (project_dir / "pyproject.toml").write_text(files["pyproject.toml"])
    (project_dir / "src" / pkg / "__init__.py").write_text(
        files[f"src/{pkg}/__init__.py"]
    )
    (project_dir / "src" / pkg / "client.py").write_text(files[f"src/{pkg}/client.py"])
    (project_dir / "src" / pkg / "source.py").write_text(files[f"src/{pkg}/source.py"])

    wheel_path = _build_wheel(project_dir)

    # the wheel packages exactly the generated modules, at the package root
    with zipfile.ZipFile(wheel_path) as zf:
        names = set(zf.namelist())
    assert f"{pkg}/__init__.py" in names
    assert f"{pkg}/client.py" in names
    assert f"{pkg}/source.py" in names

    load_script = tmp_path / "load_from_wheel.py"
    load_script.write_text(_LOAD_FROM_WHEEL_SCRIPT)

    # Executor working directory: nothing about `pkg` is importable from
    # here except whatever sys.path entry the script itself is given.
    executor_cwd = tmp_path / "executor_cwd"
    executor_cwd.mkdir()

    def load(whl_arg: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(load_script), whl_arg, pkg, source_class_name],
            capture_output=True,
            text=True,
            cwd=str(executor_cwd),
        )

    # --- positive: only the built .whl on sys.path, like a real executor
    # with `environment.dependencies` installing it.
    positive = load(str(wheel_path))
    assert positive.returncode == 0, positive.stderr
    assert json.loads(positive.stdout) == [
        {"id": 1, "title": "hello from the executor"}
    ]

    # --- negative control: nothing on sys.path at all — proves the import
    # genuinely depends on the wheel being present, not on some ambient
    # sys.path entry (e.g. an editable install) making the test a tautology.
    negative = load("")
    assert negative.returncode != 0
    assert "ModuleNotFoundError" in negative.stderr
    assert pkg in negative.stderr


# --- executor wheel simulation: auth secret refs -----------------------------
# Regression test for a critical bug in the wheel-packaging fix above: once
# `src/<pkg>` ships as an installed wheel, Spark's Python workers pickle the
# registered DataSource class BY REFERENCE and reconstruct it with a fresh
# `import <pkg>.client` — which runs with no SparkSession/dbutils available.
# A module-level `API_TOKEN: str = _dbx_secret(...)`/`_uc_secret(...)` call in
# `client.py` (the by-value-pickling-era design) would therefore raise on
# EVERY read once bundled as a wheel. The fix: bundles' `client.py` keeps its
# secret-ref slots typed `str | None = None` (the helper function defs are
# still emitted); `pipelines/<stream>.py` resolves the ref driver-side (the
# only place with a session) and threads the value through as a DataSource
# reader option (`secret_<VAR>`); `<pkg>.source` installs it onto
# `<pkg>.client`'s globals — in `schema()` AND `reader()`, so schema
# inference is covered too — before any fetch call runs. If a slot is still
# `None` once the fetch path actually reads it (the pipeline never resolved
# and installed it), the generated code raises a `RuntimeError` naming the
# slot instead of silently sending `None`/a placeholder to the real API.
#
# Simulated with the same two-subprocess wheel setup as above, but standing
# in for the driver's resolution step by constructing the DataSource
# directly with the option a real driver would have produced (Spark hands
# `DataSource.__init__` a case-insensitive options mapping that lowercases
# every key on the way in, so the option is passed pre-lowercased here too —
# exercising the `.upper()` reconstruction in `_apply_secret_options`
# exactly as it would see it for real). The negative control (no secret
# option at all) proves the positive result genuinely depends on the options
# channel: with nothing supplied, the read raises instead of silently
# succeeding some other way.

_LOAD_FROM_WHEEL_WITH_SECRET_SCRIPT = """
import importlib
import json
import sys

whl_path, pkg, source_class_name, options_json = (
    sys.argv[1],
    sys.argv[2],
    sys.argv[3],
    sys.argv[4],
)
if whl_path:
    sys.path.insert(0, whl_path)

options = json.loads(options_json)


class _Field:
    def __init__(self, name):
        self.name = name


class _Schema:
    def __init__(self, names):
        self.fields = [_Field(name) for name in names]


source_module = importlib.import_module(f"{pkg}.source")
source_cls = getattr(source_module, source_class_name)
# Mirrors Spark exactly: the DataSource instance is constructed with the
# options mapping, then .reader(schema) is called on that SAME instance —
# both happen in this one worker process, with nothing else of <pkg> on
# sys.path but the wheel.
instance = source_cls(options)
reader = instance.reader(_Schema(["id", "title"]))
records = list(reader.read(None))
sys.stdout.write(json.dumps(records))
"""


def test_bundle_wheel_secret_ref_resolved_driver_side_and_shipped_via_options(
    tmp_path, http_server
):
    seen_auth_headers: list = []

    def route(query, headers, body):
        seen_auth_headers.append(headers.get("Authorization"))
        return 200, [{"id": 1, "title": "hello"}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        name="posts",
        path="/posts",
        auth=AuthConfig(
            type="bearer", secret=SecretRef(scope="my-scope", key="my-key")
        ),
    )

    pkg = "execsim_secret_pkg"
    files = generate_bundle(config, project_name=pkg, catalog="main", schema="raw")
    source_class_name = f"{_pascal_case(pkg)}Source"

    # client.py never calls _dbx_secret at module level for a bundle — that
    # is the actual bug this test guards against (it would raise on a
    # session-less worker). pipelines/posts.py resolves it driver-side
    # instead.
    client_py = files[f"src/{pkg}/client.py"]
    assert "API_TOKEN: str | None = None" in client_py
    assert '_dbx_secret("my-scope", "my-key")' not in client_py
    assert (
        "def _dbx_secret(" in client_py
    )  # helper still emitted, for the driver to call
    pipeline_py = files["pipelines/posts.py"]
    assert 'client._dbx_secret("my-scope", "my-key")' in pipeline_py
    assert ".options(**_secret_options)" in pipeline_py

    project_dir = tmp_path / "bundle_project"
    (project_dir / "src" / pkg).mkdir(parents=True)
    (project_dir / "pyproject.toml").write_text(files["pyproject.toml"])
    (project_dir / "src" / pkg / "__init__.py").write_text(
        files[f"src/{pkg}/__init__.py"]
    )
    (project_dir / "src" / pkg / "client.py").write_text(client_py)
    (project_dir / "src" / pkg / "source.py").write_text(files[f"src/{pkg}/source.py"])

    wheel_path = _build_wheel(project_dir)

    load_script = tmp_path / "load_from_wheel_secret.py"
    load_script.write_text(_LOAD_FROM_WHEEL_WITH_SECRET_SCRIPT)
    executor_cwd = tmp_path / "executor_cwd_secret"
    executor_cwd.mkdir()

    def load(options: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(load_script),
                str(wheel_path),
                pkg,
                source_class_name,
                json.dumps(options),
            ],
            capture_output=True,
            text=True,
            cwd=str(executor_cwd),
        )

    # --- positive: the driver-resolved secret arrives as a reader option,
    # pre-lowercased exactly like Spark's real CaseInsensitiveDict would
    # hand it over.
    positive = load({"secret_api_token": "resolved-secret-value"})
    assert positive.returncode == 0, positive.stderr
    assert json.loads(positive.stdout) == [[1, "hello"]]
    assert seen_auth_headers[-1] == "Bearer resolved-secret-value"

    # --- negative control: no secret option supplied at all -> API_TOKEN is
    # still None when the fetch path reads it, so the read raises instead of
    # silently sending "None"/a placeholder to the real API, proving the
    # positive result above genuinely depends on the options channel.
    negative = load({})
    assert negative.returncode != 0
    assert "RuntimeError" in negative.stderr
    assert (
        "API_TOKEN was not installed by the pipeline — resolve secrets on"
        " the driver and pass them as reader options"
    ) in negative.stderr
    # no second request ever reached the server — the guard raised first
    assert len(seen_auth_headers) == 1


# --- executor wheel simulation: OPT_* placeholders inside HEADERS/PARAMS/PATH
# Critical gap in the secret-ref fix above: `_apply_secret_options` setattrs
# the driver-resolved value onto the `OPT_*` module global itself, but
# HEADERS/PARAMS/PATH that embed that placeholder (e.g. a header
# `{"X-Tenant": "{{ options.tenant_id }}"}`) are dict/f-string literals
# evaluated ONCE at import time, with `OPT_*` still `None` then — the later
# setattr never reaches them, so a bundled read would silently ship "None"
# to the real API instead of the resolved secret. `core.py.jinja` emits
# `_rebuild_option_literals()`, re-evaluating exactly those literals (with a
# `RuntimeError` guard if the value is still `None`), called from
# `_apply_secret_options` right after the setattr loop.


def test_bundle_wheel_option_placeholders_in_headers_and_params_resolved(
    tmp_path, http_server
):
    seen_requests: list = []

    def route(query, headers, body):
        seen_requests.append({"query": query, "headers": headers})
        return 200, [{"id": 1, "title": "hello"}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        name="posts",
        path="/posts",
        headers={"X-Tenant": "{{ options.tenant_id }}"},
        params={"team": "{{ options.team_id }}"},
        option_secrets={
            "tenant_id": SecretRef(scope="my-scope", key="tenant-id"),
            "team_id": SecretRef(scope="my-scope", key="team-id"),
        },
    )

    pkg = "execsim_opt_pkg"
    files = generate_bundle(config, project_name=pkg, catalog="main", schema="raw")
    source_class_name = f"{_pascal_case(pkg)}Source"

    client_py = files[f"src/{pkg}/client.py"]
    # the module-level literals are still None at import time...
    assert "OPT_TENANT_ID: str | None = None" in client_py
    assert "OPT_TEAM_ID: str | None = None" in client_py
    # ...but the rebuild function that re-evaluates HEADERS/PARAMS after a
    # driver-resolved value lands is emitted alongside them
    assert "def _rebuild_option_literals(" in client_py

    project_dir = tmp_path / "bundle_project"
    (project_dir / "src" / pkg).mkdir(parents=True)
    (project_dir / "pyproject.toml").write_text(files["pyproject.toml"])
    (project_dir / "src" / pkg / "__init__.py").write_text(
        files[f"src/{pkg}/__init__.py"]
    )
    (project_dir / "src" / pkg / "client.py").write_text(client_py)
    (project_dir / "src" / pkg / "source.py").write_text(files[f"src/{pkg}/source.py"])

    wheel_path = _build_wheel(project_dir)

    load_script = tmp_path / "load_from_wheel_options.py"
    load_script.write_text(_LOAD_FROM_WHEEL_WITH_SECRET_SCRIPT)
    executor_cwd = tmp_path / "executor_cwd_options"
    executor_cwd.mkdir()

    def load(options: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(load_script),
                str(wheel_path),
                pkg,
                source_class_name,
                json.dumps(options),
            ],
            capture_output=True,
            text=True,
            cwd=str(executor_cwd),
        )

    # --- positive: both driver-resolved options arrive as reader options,
    # pre-lowercased exactly like Spark's real CaseInsensitiveDict would
    # hand them over.
    positive = load(
        {
            "secret_opt_tenant_id": "real-tenant",
            "secret_opt_team_id": "real-team",
        }
    )
    assert positive.returncode == 0, positive.stderr
    assert json.loads(positive.stdout) == [[1, "hello"]]
    assert seen_requests[-1]["headers"].get("X-Tenant") == "real-tenant"
    assert seen_requests[-1]["query"].get("team") == "real-team"

    # --- negative control: no options supplied at all -> both OPT_* vars are
    # still None when the rebuild runs, so it raises instead of silently
    # shipping "None" to the real API, proving the positive result above
    # genuinely depends on the options channel (and on the rebuild actually
    # running). OPT_TEAM_ID sorts before OPT_TENANT_ID (see
    # `rebuild_guard_vars` in `generator._context`), so its guard fires
    # first.
    negative = load({})
    assert negative.returncode != 0
    assert "RuntimeError" in negative.stderr
    assert (
        "OPT_TEAM_ID was not installed by the pipeline — resolve secrets on"
        " the driver and pass them as reader options"
    ) in negative.stderr
    assert len(seen_requests) == 1


def test_bundle_wheel_option_placeholder_in_path_resolved(tmp_path, http_server):
    def ok_route(query, headers, body):
        return 200, [{"id": 1, "title": "hello"}], {}

    http_server.routes["/tenants/real-tenant/posts"] = ok_route

    config = make_config(
        base_url=http_server.url,
        name="posts",
        path="/tenants/{{ options.tenant_id }}/posts",
        option_secrets={"tenant_id": SecretRef(scope="my-scope", key="tenant-id")},
    )

    pkg = "execsim_opt_path_pkg"
    files = generate_bundle(config, project_name=pkg, catalog="main", schema="raw")
    source_class_name = f"{_pascal_case(pkg)}Source"
    client_py = files[f"src/{pkg}/client.py"]
    assert "def _rebuild_option_literals(" in client_py

    project_dir = tmp_path / "bundle_project"
    (project_dir / "src" / pkg).mkdir(parents=True)
    (project_dir / "pyproject.toml").write_text(files["pyproject.toml"])
    (project_dir / "src" / pkg / "__init__.py").write_text(
        files[f"src/{pkg}/__init__.py"]
    )
    (project_dir / "src" / pkg / "client.py").write_text(client_py)
    (project_dir / "src" / pkg / "source.py").write_text(files[f"src/{pkg}/source.py"])

    wheel_path = _build_wheel(project_dir)

    load_script = tmp_path / "load_from_wheel_path.py"
    load_script.write_text(_LOAD_FROM_WHEEL_WITH_SECRET_SCRIPT)
    executor_cwd = tmp_path / "executor_cwd_path"
    executor_cwd.mkdir()

    def load(options: dict) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                sys.executable,
                str(load_script),
                str(wheel_path),
                pkg,
                source_class_name,
                json.dumps(options),
            ],
            capture_output=True,
            text=True,
            cwd=str(executor_cwd),
        )

    # --- positive: the driver-resolved tenant id arrives as a reader
    # option; the request path actually reaching the mock server must carry
    # the resolved segment, not the frozen-at-import `None` one.
    positive = load({"secret_opt_tenant_id": "real-tenant"})
    assert positive.returncode == 0, positive.stderr
    assert json.loads(positive.stdout) == [[1, "hello"]]
    assert http_server.log[-1][1] == "/tenants/real-tenant/posts"

    # --- negative control: no option supplied -> OPT_TENANT_ID is still
    # None when the rebuild runs, so it raises instead of a request ever
    # going out with an unresolved path segment.
    negative = load({})
    assert negative.returncode != 0
    assert "RuntimeError" in negative.stderr
    assert (
        "OPT_TENANT_ID was not installed by the pipeline — resolve secrets"
        " on the driver and pass them as reader options"
    ) in negative.stderr
    assert http_server.log[-1][1] == "/tenants/real-tenant/posts"


# --- databricks.yml -----------------------------------------------------------


def test_databricks_yml_parses_with_expected_resource_keys():
    config = make_config(base_url="https://x")
    files = _bundle(config, project_name="demo", catalog="main", schema="raw")
    data = yaml.safe_load(files["databricks.yml"])

    assert data["bundle"]["name"] == "demo"

    artifact = data["artifacts"]["default"]
    assert artifact["type"] == "whl"
    assert artifact["build"] == "uv build --wheel"
    assert artifact["path"] == "."

    pipelines = data["resources"]["pipelines"]
    assert set(pipelines) == {"demo_pipeline"}
    pipeline = pipelines["demo_pipeline"]
    assert pipeline["catalog"] == "main"
    assert pipeline["schema"] == "raw"
    assert pipeline["serverless"] is True
    assert pipeline["root_path"] == "${workspace.file_path}"
    assert pipeline["libraries"] == [{"glob": {"include": "pipelines/posts.py"}}]
    assert pipeline["environment"]["dependencies"] == [
        "${workspace.root_path}/artifacts/.internal/*.whl"
    ]

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


# --- pyproject.toml -------------------------------------------------------


def _load_toml(text: str) -> dict:
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError:  # pragma: no cover - Python < 3.11
        import tomli as tomllib  # type: ignore[no-redef]

    return tomllib.loads(text)


def test_pyproject_toml_packages_the_pkg_directory():
    config = make_config(base_url="https://x")
    files = _bundle(config, project_name="demo", catalog="main", schema="raw")
    data = _load_toml(files["pyproject.toml"])

    assert data["project"]["name"] == "demo"
    assert data["project"]["version"] == "0.1.0"
    assert data["project"]["requires-python"] == ">=3.10"
    assert "requests>=2.31" in data["project"]["dependencies"]
    assert data["build-system"]["build-backend"] == "uv_build"
    assert any(req.startswith("uv_build") for req in data["build-system"]["requires"])
    # no UC secret in this config -> no azure-keyvault-secrets dependency
    assert not any(
        dep.startswith("azure-keyvault-secrets")
        for dep in data["project"]["dependencies"]
    )


def test_pyproject_toml_adds_azure_keyvault_dependency_when_uc_secret_present():
    from polymo.config import AuthConfig, UcSecretRef

    config = make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="bearer",
            uc_secret=UcSecretRef(
                credential="kv-cred",
                vault_url="https://my-vault.vault.azure.net/",
                secret_name="api-token",
            ),
        ),
    )
    files = _bundle(config, project_name="demo", catalog="main", schema="raw")
    data = _load_toml(files["pyproject.toml"])

    assert any(
        dep.startswith("azure-keyvault-secrets")
        for dep in data["project"]["dependencies"]
    )


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
