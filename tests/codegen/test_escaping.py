from __future__ import annotations

from polymo.codegen import generate, generate_core
from polymo.config import (
    AuthConfig,
    IncrementalConfig,
    PaginationConfig,
)
from tests.codegen.helpers import assert_hygiene, make_config

# Regression tests for config strings that previously got interpolated raw
# inside double-quoted strings / docstrings / comments in the generated
# script. A double quote (or a comment-breaking newline) in any of these
# values must not be able to break the generated syntax or inject code.

MALICIOUS = 'off"; import os #'


def test_pagination_param_names_with_quotes_are_escaped():
    config = make_config(
        base_url="https://api.example.com",
        pagination=PaginationConfig(
            type="offset",
            offset_param=MALICIOUS,
            limit_param='lim"; import sys #',
            page_size=10,
        ),
    )
    script = generate_core(config)
    assert_hygiene(script)
    # the payload must show up only as an escaped string literal, never as
    # live code (i.e. `import os` must not appear unescaped/unquoted)
    assert 'off\\"; import os #' in script
    assert 'lim\\"; import sys #' in script


def test_page_and_cursor_param_names_with_quotes_are_escaped():
    config = make_config(
        base_url="https://api.example.com",
        pagination=PaginationConfig(
            type="page",
            page_param='pg"; import os #',
            total_pages_header='tot"; import os #',
        ),
    )
    script = generate_core(config)
    assert_hygiene(script)

    config2 = make_config(
        base_url="https://api.example.com",
        pagination=PaginationConfig(
            type="cursor",
            cursor_param='cur"; import os #',
            cursor_header='hdr"; import os #',
        ),
    )
    script2 = generate_core(config2)
    assert_hygiene(script2)


def test_stream_name_with_quote_is_escaped_everywhere():
    config = make_config(
        base_url="https://api.example.com",
        name='po"sts',
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
    )
    script = generate(config)
    assert_hygiene(script)
    # dp table names are sanitized to valid SQL identifiers, not escaped.
    assert '@dp.table(name="po_sts")' in script
    assert 'STATE_PATH: str = "po\\"sts_state.json"' in script


def test_stream_name_with_newline_is_escaped_in_module_docstring():
    # The stream name lands in the one-line module docstring
    # (`"""Lakeflow Declarative Pipelines connector for <name>."""`) via
    # `_doc_escape`, not in any `#` comment (generated output has none left
    # that interpolate config values) — a raw embedded newline there would
    # otherwise break out of the triple-quoted docstring.
    config = make_config(
        base_url="https://api.example.com",
        name="posts\nimport os",
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
    )
    script = generate(config)
    assert_hygiene(script)
    lines = script.splitlines()
    bare_import_os = [line for line in lines if line == "import os"]
    # exactly the one legitimate top-level `import os` the incremental
    # template emits; the malicious payload must not add a second one
    assert len(bare_import_os) == 1
    assert (
        '"""Lakeflow Declarative Pipelines connector for posts\nimport os."""' in script
    )


def test_oauth_fields_with_quotes_are_escaped():
    config = make_config(
        base_url="https://api.example.com",
        auth=AuthConfig(
            type="oauth2",
            token_url='https://x/token"; import os #',
            client_id='cid"; import os #',
            scope=('read"; import os #',),
            audience='aud"; import os #',
            extra_params={'k"ey': "value"},
        ),
    )
    script = generate_core(config)
    assert_hygiene(script)


def test_incremental_cursor_fields_with_quotes_are_escaped():
    config = make_config(
        base_url="https://api.example.com",
        incremental=IncrementalConfig(
            mode='cursor"; import os #',
            cursor_param='since"; import os #',
            cursor_field='updated"; import os #',
            state_path='/tmp/st"; import os #.json',
            start_value='2024"; import os #',
            state_key='key"; import os #',
        ),
    )
    script = generate_core(config)
    assert_hygiene(script)
    assert 'STATE_PATH: str = "/tmp/st\\"; import os #.json"' in script
    assert 'STATE_KEY: str = "key\\"; import os #"' in script
    assert 'START_VALUE: str | None = "2024\\"; import os #"' in script
    assert '"mode": "cursor\\"; import os #"' in script


def test_remote_state_path_with_quotes_is_escaped():
    config = make_config(
        base_url="https://api.example.com",
        incremental=IncrementalConfig(
            mode="cursor",
            cursor_param="since",
            cursor_field="updated",
            state_path='s3://b/st"; import os #.json',
        ),
    )
    script = generate_core(config)
    assert_hygiene(script)
    assert "def _state_fs()" in script
    assert 'STATE_PATH: str = "s3://b/st\\"; import os #.json"' in script


def test_base_url_and_path_with_quotes_are_escaped():
    config = make_config(
        base_url='https://api.example.com/"; import os #',
        path='/posts/"; import os #',
    )
    script = generate_core(config)
    assert_hygiene(script)
