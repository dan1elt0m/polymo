from __future__ import annotations

from polymo.codegen import generate, generate_core
from tests.codegen.helpers import assert_hygiene, make_config, run_generated


def test_core_fetches_single_page(http_server):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}, {"id": 2}], {})
    config = make_config(base_url=http_server.url)

    module = run_generated(config)

    assert list(module.fetch_records()) == [{"id": 1}, {"id": 2}]


def test_core_has_no_forbidden_imports():
    config = make_config(base_url="https://api.example.com")
    core = generate_core(config)
    for forbidden in ("polymo", "pyspark", "jinja2", "yaml", "httpx"):
        assert f"import {forbidden}" not in core


def test_full_script_appends_dp_wiring():
    config = make_config(base_url="https://api.example.com")
    script = generate(config)
    assert_hygiene(script)
    assert script.startswith(generate_core(config))
    assert "from pyspark import pipelines as dp" in script
    assert '@dp.table(name="posts")' in script
    assert "def posts()" in script


def test_generate_exported_from_package():
    from polymo import generate as top_level_generate
    from polymo.codegen import generate

    assert top_level_generate is generate


def test_dp_table_name_is_valid_sql_identifier():
    # Derived stream names can contain hyphens (e.g. from /resource/m9d7-ebf2.json);
    # Databricks requires @dp.table names to be valid unquoted SQL identifiers.
    config = make_config(
        base_url="https://opendata.rdw.nl", name="resource_m9d7-ebf2_json"
    )
    script = generate(config)
    assert '@dp.table(name="resource_m9d7_ebf2_json")' in script
    assert "m9d7-ebf2" not in script.split("@dp.table", 1)[1]


def test_dp_table_name_symbol_only_falls_back_to_stream():
    # A name that sanitizes to nothing but underscores (e.g. "!!!" -> "___")
    # would otherwise be an ugly, collision-prone table name; fall back to
    # a real word instead.
    config = make_config(base_url="https://api.example.com", name="!!!")
    script = generate(config)
    assert '@dp.table(name="stream")' in script
