from polymo.codegen.templating import _PathFormatter, _render_template


def test_render_template_resolves_options():
    ctx = {"options": {"country": "NL"}, "params": {}, "headers": {}, "raw_params": {}}
    assert _render_template("{{ options.country }}", ctx) == "NL"


def test_path_formatter_consumes_params():
    formatter = _PathFormatter({"user_id": "42", "limit": "5"})
    assert formatter.render("/users/{user_id}/posts") == "/users/42/posts"
    assert formatter.remaining_params() == {"limit": "5"}
