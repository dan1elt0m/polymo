from __future__ import annotations

import ast

import pytest

from polymo.codegen import generate, generate_bundle, generate_core
from tests.codegen.helpers import assert_hygiene, make_config

# A stream/project name that sanitizes (via _identifier's \W -> "_" pass) to
# a bare Python keyword would otherwise get spliced in raw at every
# identifier site — `def class():`, `from class.client import ...`,
# `@dp.table(name="class")`'s function def, etc. — producing a SyntaxError
# in the emitted file. _identifier() appends a trailing "_" whenever the
# sanitized result is a hard keyword.
KEYWORD_NAMES = ["class", "import", "None", "True", "def"]


@pytest.mark.parametrize("name", KEYWORD_NAMES)
def test_generate_single_file_survives_keyword_stream_name(name):
    config = make_config(base_url="https://x", name=name)
    script = generate(config)
    ast.parse(script)
    assert_hygiene(script)
    assert f"def {name}_():" in script
    assert f"def {name}():" not in script


@pytest.mark.parametrize("name", KEYWORD_NAMES)
def test_generate_core_survives_keyword_stream_name(name):
    config = make_config(base_url="https://x", name=name)
    core = generate_core(config)
    ast.parse(core)
    assert_hygiene(core)


@pytest.mark.parametrize("name", KEYWORD_NAMES)
def test_generate_bundle_survives_keyword_project_name(name):
    config = make_config(base_url="https://x")
    files = generate_bundle(config, project_name=name, catalog="main", schema="raw")

    pkg = f"{name}_"
    assert f"src/{pkg}/client.py" in files
    assert f"src/{pkg}/source.py" in files

    client = files[f"src/{pkg}/client.py"]
    ast.parse(client)
    assert_hygiene(client)

    source = files[f"src/{pkg}/source.py"]
    ast.parse(source)
    assert_hygiene(source)
    assert "from .client import" in source

    pipeline = files["pipelines/posts.py"]
    ast.parse(pipeline)
    assert_hygiene(pipeline)
    assert f"from {pkg}.source import" in pipeline


@pytest.mark.parametrize("name", KEYWORD_NAMES)
def test_generate_bundle_survives_keyword_stream_name(name):
    config = make_config(base_url="https://x", name=name)
    files = generate_bundle(config, project_name="demo", catalog="main", schema="raw")

    stream = f"{name}_"
    pipeline_path = f"pipelines/{stream}.py"
    assert pipeline_path in files

    pipeline = files[pipeline_path]
    ast.parse(pipeline)
    assert_hygiene(pipeline)
    assert f"def {stream}():" in pipeline
    assert f"def {name}():" not in pipeline


@pytest.mark.parametrize("name", KEYWORD_NAMES)
def test_identifier_ends_with_underscore_for_keywords(name):
    from polymo.codegen.generator import _identifier

    result = _identifier(name)
    assert result.endswith("_")
    assert result == f"{name}_"
