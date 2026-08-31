from __future__ import annotations

from pathlib import Path

import pytest

from polymo.codegen import generate
from polymo.config import (
    AuthConfig,
    IncrementalConfig,
    PaginationConfig,
    PartitionConfig,
    RecordSelectorConfig,
)
from tests.codegen.helpers import assert_hygiene, make_config

GOLDEN_DIR = Path(__file__).parent / "golden"

CASES = {
    "rdw_offset": make_config(
        base_url="https://opendata.rdw.nl",
        name="gekentekende_voertuigen",
        path="/resource/m9d7-ebf2.json",
        params={"$order": "kenteken"},
        pagination=PaginationConfig(
            type="offset", page_size=1000, limit_param="$limit", offset_param="$offset"
        ),
    ),
    "bearer_cursor_selector": make_config(
        base_url="https://api.example.com",
        auth=AuthConfig(type="bearer"),
        pagination=PaginationConfig(
            type="cursor", cursor_param="after", cursor_path=("meta", "next")
        ),
        record_selector=RecordSelectorConfig(field_path=["data"]),
    ),
    "oauth_incremental_partitioned": make_config(
        base_url="https://api.example.com",
        auth=AuthConfig(
            type="oauth2", token_url="https://api.example.com/token", client_id="cid"
        ),
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
        schema="id BIGINT, updated STRING",
    ),
    "streaming_page": make_config(
        base_url="https://api.example.com",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    ),
    "maileon_basic_header": make_config(
        base_url="https://api.maileon.com/1.0",
        name="contacts",
        path="/contacts",
        headers={
            "Authorization": "Basic {{ options.api_key_b64 }}",
            "Accept": "application/vnd.maileon.api+xml",
        },
        pagination=PaginationConfig(
            type="page",
            page_param="page_index",
            start_page=0,
            limit_param="page_size",
            page_size=100,
            total_pages_header="X-Pages",
        ),
        response_format="xml",
        xml_record_path=".//contact",
    ),
    "maileon_xml": make_config(
        base_url="https://api.maileon.com/1.0",
        name="contacts",
        path="/contacts",
        headers={
            "Authorization": "Basic REPLACE_ME_BASE64",
            "Accept": "application/vnd.maileon.api+xml",
        },
        pagination=PaginationConfig(
            type="page",
            page_param="page_index",
            start_page=0,
            limit_param="page_size",
            page_size=100,
            total_pages_header="X-Pages",
        ),
        response_format="xml",
        xml_record_path=".//contact",
    ),
}


@pytest.mark.parametrize("case", CASES)
def test_golden(case):
    script = generate(CASES[case])
    assert_hygiene(script)
    golden = GOLDEN_DIR / f"{case}.py"
    if not golden.exists():
        GOLDEN_DIR.mkdir(exist_ok=True)
        golden.write_text(script)
        pytest.skip(f"golden seeded: {golden}")
    assert script == golden.read_text(), (
        f"generated output changed; if intended, delete {golden} and rerun"
    )
