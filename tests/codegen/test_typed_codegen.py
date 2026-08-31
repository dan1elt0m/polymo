"""Every generated def/class carries type annotations (user request:
"zorg dat de gegenereerde code python typed is").

Checks representative generated scripts (batch/plain, batch+schema,
windowed, incremental, streaming, oauth2, xml) for the annotated
signatures specified by the upgrade, a single top-of-file typing import,
and (as always) that the output still passes ast.parse + ruff.
"""

from __future__ import annotations

import ast

from polymo.codegen import generate
from polymo.config import (
    AuthConfig,
    IncrementalConfig,
    PaginationConfig,
    PartitionConfig,
)
from tests.codegen.helpers import assert_hygiene, make_config


def test_single_typing_import_at_top_no_schema():
    config = make_config(base_url="https://x")
    script = generate(config)
    assert_hygiene(script)
    # exactly one `from typing import ...` line, and it's the only import
    # of `typing` — everything downstream (including the dp wiring
    # concatenated after core) shares this one binding.
    assert script.count("from typing import") == 1
    assert "from typing import Any, Iterator" in script


def test_module_level_functions_are_annotated():
    config = make_config(base_url="https://x")
    script = generate(config)
    assert_hygiene(script)
    ast.parse(script)

    assert (
        "def fetch_records(extra_params: dict[str, Any] | None = None, path: str"
        " | None = None) -> Iterator[dict[str, Any]]:" in script
    )
    assert "def _records(payload: Any) -> list[dict[str, Any]]:" in script
    assert (
        "def _request(session: requests.Session, url: str, params: dict[str, Any]"
        " | None) -> requests.Response:" in script
    )
    assert "def _should_retry(status: int) -> bool:" in script


def test_constants_are_annotated():
    config = make_config(base_url="https://x")
    script = generate(config)
    assert_hygiene(script)
    assert "PARAMS: dict[str, Any] =" in script
    assert "HEADERS: dict[str, str] =" in script
    assert "TIMEOUT: float = 30.0" in script
    assert "BASE_URL: str =" in script
    assert "PATH: str =" in script


def test_schema_ddl_reader_is_typed():
    config = make_config(base_url="https://x", schema="id BIGINT, name STRING")
    script = generate(config)
    assert_hygiene(script)
    ast.parse(script)
    assert "SCHEMA: str =" in script
    assert "def schema(self) -> str:" in script
    assert "def read(self, partition) -> Iterator[tuple]:" in script


def test_inferred_schema_cell_and_infer_schema_typed():
    config = make_config(base_url="https://x")
    script = generate(config)
    assert_hygiene(script)
    assert "def _infer_schema() -> str:" in script
    assert "def _cell(value: Any) -> Any:" in script


def test_windowed_partitions_typed():
    config = make_config(
        base_url="https://x",
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
    )
    script = generate(config)
    assert_hygiene(script)
    ast.parse(script)
    assert "WINDOWS: list[dict[str, Any]] =" in script
    assert "def partitions(self) -> list[InputPartition]:" in script


def test_incremental_state_helpers_typed():
    config = make_config(
        base_url="https://x",
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
    )
    script = generate(config)
    assert_hygiene(script)
    ast.parse(script)
    assert "STATE_PATH: str =" in script
    assert "def _read_state() -> dict[str, Any]:" in script
    assert "def _write_state(cursor: Any) -> None:" in script
    assert "LAST_CURSOR: dict[str, Any] =" in script


def test_oauth2_get_token_typed():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="oauth2", token_url="https://x/token", client_id="cid"),
    )
    script = generate(config)
    assert_hygiene(script)
    ast.parse(script)
    assert "CLIENT_SECRET: str =" in script
    assert "TOKEN_URL: str =" in script
    assert "def get_token() -> str:" in script


def test_api_key_and_bearer_constants_typed():
    bearer_script = generate(
        make_config(base_url="https://x", auth=AuthConfig(type="bearer"))
    )
    assert_hygiene(bearer_script)
    assert "API_TOKEN: str =" in bearer_script

    api_key_script = generate(
        make_config(
            base_url="https://x",
            auth=AuthConfig(type="api_key", api_key_in="header", api_key_name="X-Key"),
        )
    )
    assert_hygiene(api_key_script)
    assert "API_KEY: str =" in api_key_script


def test_streaming_typed_signatures():
    config = make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    )
    script = generate(config)
    assert_hygiene(script)
    ast.parse(script)
    assert "def fetch_page(page_index: int) -> list[dict[str, Any]]:" in script
    assert "def initialOffset(self) -> dict[str, Any]:" in script
    assert (
        "def read(self, start: dict[str, Any]) -> tuple[Iterator[tuple], dict[str, Any]]:"
        in script
    )
    assert (
        "def readBetweenOffsets(self, start: dict[str, Any], end: dict[str, Any])"
        " -> Iterator[tuple]:" in script
    )


def test_xml_records_typed():
    config = make_config(
        base_url="https://x",
        response_format="xml",
        xml_record_path=".//item",
    )
    script = generate(config)
    assert_hygiene(script)
    ast.parse(script)
    assert "def _records(root: ET.Element) -> list[dict[str, Any]]:" in script
    assert "XML_RECORD_PATH: str =" in script
