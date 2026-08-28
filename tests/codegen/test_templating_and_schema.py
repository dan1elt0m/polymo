from __future__ import annotations

from polymo.codegen import generate, generate_core
from tests.codegen.helpers import assert_hygiene, make_config


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
    assert "schema=SCHEMA" in script


def test_no_schema_falls_back_to_inference():
    config = make_config(base_url="https://x")
    script = generate(config)
    assert "SCHEMA" not in script
