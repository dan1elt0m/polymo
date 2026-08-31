from __future__ import annotations

import pytest

from polymo.codegen import CodegenError, generate_core
from polymo.config import PaginationConfig, RecordSelectorConfig
from tests.codegen.helpers import assert_hygiene, make_config, run_generated


def test_xml_records_parsed(http_server):
    body = (
        "<contacts>"
        '<contact id="7"><email>a@b.nl</email><permission>NONE</permission></contact>'
        '<contact id="8"><email>c@d.nl</email><permission>DOI</permission></contact>'
        "</contacts>"
    )
    http_server.routes["/contacts"] = lambda q, h, b: (
        200,
        body,
        {"Content-Type": "application/vnd.maileon.api+xml"},
    )
    config = make_config(
        base_url=http_server.url,
        name="contacts",
        path="/contacts",
        response_format="xml",
        xml_record_path=".//contact",
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [
        {"@id": "7", "email": "a@b.nl", "permission": "NONE"},
        {"@id": "8", "email": "c@d.nl", "permission": "DOI"},
    ]


def test_xml_page_pagination_with_total_pages_header(http_server):
    # The Maileon shape: page_index/page_size pagination, total page count
    # reported via an X-Pages response header, XML body.
    pages = {
        0: [{"id": "1"}, {"id": "2"}],
        1: [{"id": "3"}],
    }

    def route(query, headers, body):
        page = int(query.get("page_index", "0"))
        contacts = pages.get(page, [])
        items = "".join(
            f'<contact id="{c["id"]}"><email>e{c["id"]}@x.nl</email></contact>'
            for c in contacts
        )
        return (
            200,
            f"<contacts>{items}</contacts>",
            {"Content-Type": "application/vnd.maileon.api+xml", "X-Pages": "2"},
        )

    http_server.routes["/contacts"] = route
    config = make_config(
        base_url=http_server.url,
        name="contacts",
        path="/contacts",
        response_format="xml",
        xml_record_path=".//contact",
        pagination=PaginationConfig(
            type="page",
            page_param="page_index",
            start_page=0,
            limit_param="page_size",
            page_size=2,
            total_pages_header="X-Pages",
        ),
    )
    module = run_generated(config)
    assert list(module.fetch_records()) == [
        {"@id": "1", "email": "e1@x.nl"},
        {"@id": "2", "email": "e2@x.nl"},
        {"@id": "3", "email": "e3@x.nl"},
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param(
            {
                "pagination": PaginationConfig(
                    type="cursor", cursor_param="c", cursor_path=("meta", "next")
                )
            },
            id="cursor_path",
        ),
        pytest.param(
            {
                "pagination": PaginationConfig(
                    type="cursor", cursor_param="c", next_url_path=("links", "next")
                )
            },
            id="next_url_path",
        ),
        pytest.param(
            {
                "pagination": PaginationConfig(
                    type="page", page_param="page", total_pages_path=("meta", "pages")
                )
            },
            id="total_pages_path",
        ),
        pytest.param(
            {
                "pagination": PaginationConfig(
                    type="none", total_records_path=("meta", "count")
                )
            },
            id="total_records_path",
        ),
        pytest.param(
            {"record_selector": RecordSelectorConfig(field_path=["data"])},
            id="record_selector_field_path",
        ),
    ],
)
def test_xml_rejects_json_path_features(kwargs):
    config = make_config(
        base_url="https://api.example.com",
        response_format="xml",
        xml_record_path=".//contact",
        **kwargs,
    )
    with pytest.raises(CodegenError):
        generate_core(config)


@pytest.mark.parametrize(
    "pagination",
    [
        PaginationConfig(type="none"),
        PaginationConfig(
            type="offset", offset_param="offset", page_size=2, limit_param="limit"
        ),
        PaginationConfig(
            type="page",
            page_param="page_index",
            limit_param="page_size",
            page_size=2,
            total_pages_header="X-Pages",
        ),
        PaginationConfig(
            type="cursor", cursor_param="c", cursor_header="X-Next-Cursor"
        ),
        PaginationConfig(type="link_header"),
    ],
)
def test_xml_hygiene_across_pagination_variants(pagination):
    config = make_config(
        base_url="https://api.example.com",
        response_format="xml",
        xml_record_path=".//contact",
        pagination=pagination,
    )
    script = generate_core(config)
    assert_hygiene(script)
    assert "import xml.etree.ElementTree as ET" in script
    assert "response.json()" not in script
