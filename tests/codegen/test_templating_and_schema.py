from __future__ import annotations

from polymo.codegen import generate, generate_core
from tests.codegen.helpers import assert_hygiene, make_config, run_generated


def test_params_templates_resolved_at_generation_time():
    config = make_config(
        base_url="https://x",
        params={"country": "{{ options.country }}"},
        options={"country": "NL"},
    )
    core = generate_core(config)
    assert '"country": "NL"' in core
    assert "{{" not in core


def test_schema_ddl_emitted_in_dp_wiring():
    config = make_config(base_url="https://x", schema="id BIGINT, name STRING")
    script = generate(config)
    assert_hygiene(script)
    assert 'SCHEMA = "id BIGINT, name STRING"' in script
    # the inline DataSource's schema() returns the explicit DDL directly,
    # no runtime inference needed
    assert "return SCHEMA" in script
    assert "_infer_schema" not in script


def test_no_schema_falls_back_to_inference():
    # With no explicit DDL, the DataSource's schema() must still return
    # something (Spark's custom Data Source API has no equivalent of
    # createDataFrame's automatic dtype inference from Python objects), so
    # the generated script samples a few records and derives a DDL itself.
    config = make_config(base_url="https://x")
    script = generate(config)
    assert "SCHEMA =" not in script
    assert "def _infer_schema():" in script
    assert "return _infer_schema()" in script


def test_curly_brace_path_placeholder_resolved_at_generation_time():
    config = make_config(
        base_url="https://x",
        path="/users/{user_id}/posts",
        params={"user_id": "42", "limit": "5"},
    )
    core = generate_core(config)
    assert 'PATH = "/users/{user_id}/posts"' not in core
    assert 'PATH = "/users/42/posts"' in core
    assert '"limit": "5"' in core
    assert '"user_id"' not in core


def test_curly_brace_path_placeholder_used_in_request(http_server):
    http_server.routes["/users/42/posts"] = lambda q, h, b: (200, [{"id": 1}], {})
    config = make_config(
        base_url=http_server.url,
        path="/users/{user_id}/posts",
        params={"user_id": "42", "limit": "5"},
    )

    module = run_generated(config)

    assert list(module.fetch_records()) == [{"id": 1}]
    method, path, _headers = http_server.log[-1]
    assert method == "GET"
    assert path.startswith("/users/42/posts")
    assert "user_id" not in path
