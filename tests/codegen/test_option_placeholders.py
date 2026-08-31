from __future__ import annotations

from polymo.codegen import generate_core
from tests.codegen.helpers import assert_hygiene, make_config, run_generated

# Regression coverage for Phase 3 Task 10: a `{{ options.<name> }}` reference
# whose name is NOT in `config.options` (the normal case via /api/generate,
# which passes no options at all) must generate an `OPT_<NAME>` placeholder
# variable instead of crashing with a jinja2 UndefinedError.


def test_missing_option_becomes_placeholder_variable():
    config = make_config(
        base_url="https://api.maileon.com/1.0",
        headers={"Authorization": "Basic {{ options.api_key_b64 }}"},
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'OPT_API_KEY_B64 = "REPLACE_ME"' in core
    assert 'HEADERS: dict = {"Authorization": f"Basic {OPT_API_KEY_B64}"}' in core


def test_missing_option_placeholder_present_in_dbutils_comment():
    config = make_config(
        base_url="https://x",
        headers={"Authorization": "Basic {{ options.api_key_b64 }}"},
    )
    core = generate_core(config)
    assert "dbutils.secrets.get" in core
    assert "{{ options.* }}" in core


def test_missing_option_placeholder_used_at_request_time(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Basic abc"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        headers={"Authorization": "Basic {{ options.api_key_b64 }}"},
    )
    module = run_generated(config, override_globals={"OPT_API_KEY_B64": "abc"})
    assert list(module.fetch_records()) == [{"id": 1}]


def test_missing_option_placeholder_defaults_to_replace_me(http_server):
    def route(query, headers, body):
        assert headers.get("Authorization") == "Basic REPLACE_ME"
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        headers={"Authorization": "Basic {{ options.api_key_b64 }}"},
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [{"id": 1}]


def test_option_present_still_inlines_directly_no_placeholder():
    config = make_config(
        base_url="https://x",
        headers={"Authorization": "Basic {{ options.api_key_b64 }}"},
        options={"api_key_b64": "c3VwZXJzZWNyZXQ="},
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'HEADERS: dict = {"Authorization": "Basic c3VwZXJzZWNyZXQ="}' in core
    assert "OPT_" not in core
    assert "{{" not in core


def test_missing_option_in_path_becomes_fstring_path():
    config = make_config(
        base_url="https://x",
        path="/accounts/{{ options.account_id }}/contacts",
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'OPT_ACCOUNT_ID = "REPLACE_ME"' in core
    assert 'PATH = f"/accounts/{OPT_ACCOUNT_ID}/contacts"' in core


def test_missing_option_dict_key_style_reference():
    config = make_config(
        base_url="https://x",
        headers={"Authorization": 'Basic {{ options["api_key_b64"] }}'},
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'OPT_API_KEY_B64 = "REPLACE_ME"' in core


def test_multiple_missing_options_each_get_a_placeholder():
    config = make_config(
        base_url="https://x",
        headers={
            "Authorization": "Basic {{ options.api_key_b64 }}",
            "X-Tenant": "{{ options.tenant_id }}",
        },
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'OPT_API_KEY_B64 = "REPLACE_ME"' in core
    assert 'OPT_TENANT_ID = "REPLACE_ME"' in core


def test_no_placeholders_emitted_when_no_option_refs():
    config = make_config(base_url="https://x")
    core = generate_core(config)
    assert "OPT_" not in core
    assert "options.*" not in core


def test_brace_and_option_marker_mixed_renders_valid_fstring():
    config = make_config(
        base_url="https://x",
        params={"q": "{literal}-{{ options.suffix }}"},
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'PARAMS: dict = {"q": f"{{literal}}-{OPT_SUFFIX}"}' in core


def test_option_value_with_quotes_and_braces_escapes_safely_in_fstring(http_server):
    def route(query, headers, body):
        assert headers.get("X-Weird") == 'preva"lue{with}bracespost'
        return 200, [{"id": 1}], {}

    http_server.routes["/posts"] = route
    config = make_config(
        base_url=http_server.url,
        headers={"X-Weird": "pre{{ options.weird }}post"},
    )
    module = run_generated(config, override_globals={"OPT_WEIRD": 'va"lue{with}braces'})
    assert list(module.fetch_records()) == [{"id": 1}]
