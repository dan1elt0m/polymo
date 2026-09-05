"""Every connector option, exercised against public APIs through Spark.

The unit suite proves each option against a local mock server. This suite
closes the remaining gap: the *unmodified* `generate()` output is exec'd,
its Python Data Source (`DataSource` / `DataSourceReader` /
`SimpleDataSourceStreamReader`, PySpark 4) is read back through
`spark.read.format(...)` on a real local SparkSession, and the API on the
other end is a real one, with its real pagination headers, envelopes, XML
namespaces and error codes.

Which API proves what:

- jsonplaceholder.typicode.com: plain reads, schema inference, offset and
  page pagination (`_start`/`_page`/`_limit`, `X-Total-Count`), endpoint
  and parameter-range partitions, record filters, streaming, bundles.
- pokeapi.co: offset pagination with a `count` total, `next` URL cursors.
- rickandmortyapi.com: page pagination with `info.pages`, nested records.
- gitlab.com: `X-Total-Pages` page fan-out.
- api.github.com: RFC 5988 `Link` headers, incremental `since` cursors on a
  nested timestamp (uses `GITHUB_TOKEN` as a bearer token when set).
- en.wikipedia.org: cursor pagination with the cursor in the body.
- httpbin.org: request echo, which is the only way to *see* what left the
  script: bearer / API-key / OAuth2 client-credentials auth, static and
  option-placeholder headers and params, filter pushdown, retries.
- ecb.europa.eu / export.arxiv.org: XML with attributes, namespaces and
  child elements.

Opt-in: `POLYMO_LIVE=1 pytest tests/live` (see tests/live/conftest.py).
Every request carries a descriptive User-Agent and the whole run stays
under ~80 requests, so it is polite to the APIs it borrows.
"""

from __future__ import annotations

import json
import math
import os
import shutil
import time

import pytest
import requests
from pyspark.sql.functions import col

from polymo.codegen import generate, generate_bundle
from polymo.config import (
    AuthConfig,
    BackoffConfig,
    ErrorHandlerConfig,
    IncrementalConfig,
    PaginationConfig,
    PartitionConfig,
    RecordSelectorConfig,
)
from tests.live.helpers import (
    USER_AGENT,
    exec_script,
    github_auth,
    live_config,
    read_batch,
    registered_format,
)

pytestmark = [pytest.mark.live, pytest.mark.spark]

JSONPLACEHOLDER = "https://jsonplaceholder.typicode.com"
POKEAPI = "https://pokeapi.co/api/v2"
RICK_AND_MORTY = "https://rickandmortyapi.com/api"
HTTPBIN = "https://httpbin.org"
GITHUB = "https://api.github.com"
GITLAB = "https://gitlab.com/api/v4"
WIKIPEDIA = "https://en.wikipedia.org/w"
ECB = "https://www.ecb.europa.eu"
ARXIV = "https://export.arxiv.org"

ATOM = "{http://www.w3.org/2005/Atom}"
EUROFXREF = "{http://www.ecb.int/vocabulary/2002-08-01/eurofxref}"


def _expect(url: str, **params):
    """Fetch the value a test compares against, independently of polymo."""
    headers = {"User-Agent": USER_AGENT}
    token = os.environ.get("GITHUB_TOKEN")
    if token and url.startswith(GITHUB):
        headers["Authorization"] = f"Bearer {token}"
    response = requests.get(url, params=params, headers=headers, timeout=30)
    response.raise_for_status()
    return response


def _partition_sizes(df) -> list[int]:
    return df.rdd.glom().map(len).collect()


# --- plain reads and schema ---------------------------------------------------


def test_single_page_infers_schema_from_sampled_records(spark_session):
    config = live_config(
        base_url=JSONPLACEHOLDER, name="live_posts", path="/posts", params={"_limit": 5}
    )
    df = read_batch(spark_session, config)
    assert dict(df.dtypes) == {
        "userId": "bigint",
        "id": "bigint",
        "title": "string",
        "body": "string",
    }
    assert [row.id for row in df.collect()] == [1, 2, 3, 4, 5]


def test_explicit_nested_schema_picks_declared_fields_only(spark_session):
    config = live_config(
        base_url=JSONPLACEHOLDER,
        name="live_users",
        path="/users",
        schema=(
            "id INT, name STRING,"
            " address STRUCT<city: STRING, geo: STRUCT<lat: STRING, lng: STRING>>,"
            " company STRUCT<name: STRING>"
        ),
    )
    rows = read_batch(spark_session, config).collect()
    assert len(rows) == 10
    first = next(row for row in rows if row.id == 1)
    assert first.name == "Leanne Graham"
    assert first.address.city == "Gwenborough"
    assert first.address.geo.lat == "-37.3159"
    assert first.company.name == "Romaguera-Crona"


def test_record_filter_drops_records_before_they_reach_spark(spark_session):
    config = live_config(
        base_url=JSONPLACEHOLDER,
        name="live_posts_filtered",
        path="/posts",
        params={"_limit": 30},
        record_selector=RecordSelectorConfig(record_filter="record.get('userId') == 2"),
        schema="id INT, userId INT",
    )
    rows = read_batch(spark_session, config).collect()
    assert {row.userId for row in rows} == {2}
    assert sorted(row.id for row in rows) == list(range(11, 21))


# --- pagination ---------------------------------------------------------------


def test_offset_pagination_walks_until_an_empty_page(spark_session):
    expected = _expect(f"{POKEAPI}/berry", limit=1).json()["count"]
    config = live_config(
        base_url=POKEAPI,
        name="live_berries",
        path="/berry",
        pagination=PaginationConfig(
            type="offset", offset_param="offset", limit_param="limit", page_size=20
        ),
        schema="name STRING, url STRING",
    )
    names = [row.name for row in read_batch(spark_session, config).collect()]
    assert len(names) == expected
    assert len(set(names)) == expected


def test_offset_pagination_honours_start_offset(spark_session):
    config = live_config(
        base_url=JSONPLACEHOLDER,
        name="live_posts_tail",
        path="/posts",
        pagination=PaginationConfig(
            type="offset",
            offset_param="_start",
            limit_param="_limit",
            page_size=4,
            start_offset=90,
        ),
        schema="id INT",
    )
    ids = sorted(row.id for row in read_batch(spark_session, config).collect())
    assert ids == list(range(91, 101))


def test_page_pagination_stops_at_total_pages_path(spark_session):
    info = _expect(f"{RICK_AND_MORTY}/episode").json()["info"]
    config = live_config(
        base_url=RICK_AND_MORTY,
        name="live_episodes",
        path="/episode",
        pagination=PaginationConfig(
            type="page", page_param="page", total_pages_path=("info", "pages")
        ),
        record_selector=RecordSelectorConfig(field_path=["results"]),
        schema="id INT, name STRING, episode STRING, characters ARRAY<STRING>",
    )
    rows = read_batch(spark_session, config).collect()
    assert len(rows) == info["count"]
    pilot = next(row for row in rows if row.id == 1)
    assert (pilot.name, pilot.episode) == ("Pilot", "S01E01")
    assert all(
        url.startswith(f"{RICK_AND_MORTY}/character/") for url in pilot.characters
    )


def test_cursor_pagination_follows_next_url_in_body(spark_session):
    expected = _expect(f"{POKEAPI}/berry", limit=1).json()["count"]
    config = live_config(
        base_url=POKEAPI,
        name="live_berries_next",
        path="/berry",
        params={"limit": 30},
        pagination=PaginationConfig(type="cursor", next_url_path=("next",)),
        record_selector=RecordSelectorConfig(field_path=["results"]),
        schema="name STRING",
    )
    names = [row.name for row in read_batch(spark_session, config).collect()]
    assert len(names) == len(set(names)) == expected


def test_cursor_pagination_sends_body_cursor_back_as_param(spark_session):
    expected = {
        page["title"]
        for page in _expect(
            f"{WIKIPEDIA}/api.php",
            action="query",
            list="allpages",
            apprefix="Databricks",
            aplimit=50,
            format="json",
        ).json()["query"]["allpages"]
    }
    assert len(expected) >= 2, "need at least two pages to exercise the cursor"
    config = live_config(
        base_url=WIKIPEDIA,
        name="live_wiki_pages",
        path="/api.php",
        params={
            "action": "query",
            "list": "allpages",
            "apprefix": "Databricks",
            "aplimit": 1,
            "format": "json",
        },
        pagination=PaginationConfig(
            type="cursor",
            cursor_param="apcontinue",
            cursor_path=("continue", "apcontinue"),
        ),
        record_selector=RecordSelectorConfig(field_path=["query", "allpages"]),
        schema="pageid BIGINT, ns INT, title STRING",
    )
    rows = read_batch(spark_session, config).collect()
    assert {row.title for row in rows} == expected
    assert len(rows) == len(expected)


def test_link_header_pagination_follows_rel_next(spark_session):
    auth, placeholders = github_auth()
    expected = {
        tag["name"]
        for tag in _expect(f"{GITHUB}/repos/dan1elt0m/polymo/tags", per_page=100).json()
    }
    assert len(expected) > 10, "need more than one page of tags"
    config = live_config(
        base_url=GITHUB,
        name="live_polymo_tags",
        path="/repos/dan1elt0m/polymo/tags",
        params={"per_page": 10},
        auth=auth,
        pagination=PaginationConfig(type="link_header"),
        schema="name STRING, commit STRUCT<sha: STRING>",
    )
    rows = read_batch(spark_session, config, **placeholders).collect()
    assert {row.name for row in rows} == expected
    assert len(rows) == len(expected)
    assert all(len(row.commit.sha) == 40 for row in rows)


# --- partitioning -------------------------------------------------------------


def test_pagination_fanout_from_total_records_path(spark_session):
    count = _expect(f"{POKEAPI}/berry", limit=1).json()["count"]
    config = live_config(
        base_url=POKEAPI,
        name="live_berries_fanout",
        path="/berry",
        pagination=PaginationConfig(
            type="offset",
            offset_param="offset",
            limit_param="limit",
            page_size=20,
            total_records_path=("count",),
        ),
        partition=PartitionConfig(strategy="pagination"),
        schema="name STRING",
    )
    df = read_batch(spark_session, config)
    assert df.rdd.getNumPartitions() == math.ceil(count / 20)
    names = [row.name for row in df.collect()]
    assert len(names) == len(set(names)) == count


def test_pagination_fanout_from_total_pages_path(spark_session):
    info = _expect(f"{RICK_AND_MORTY}/episode").json()["info"]
    config = live_config(
        base_url=RICK_AND_MORTY,
        name="live_episodes_fanout",
        path="/episode",
        pagination=PaginationConfig(
            type="page",
            page_param="page",
            page_size=20,
            total_pages_path=("info", "pages"),
        ),
        partition=PartitionConfig(strategy="pagination"),
        record_selector=RecordSelectorConfig(field_path=["results"]),
        schema="id INT, name STRING",
    )
    df = read_batch(spark_session, config)
    assert df.rdd.getNumPartitions() == info["pages"]
    assert sorted(row.id for row in df.collect()) == list(range(1, info["count"] + 1))


def test_pagination_fanout_from_total_records_header(spark_session):
    config = live_config(
        base_url=JSONPLACEHOLDER,
        name="live_posts_fanout",
        path="/posts",
        pagination=PaginationConfig(
            type="page",
            page_param="_page",
            limit_param="_limit",
            page_size=30,
            total_records_header="X-Total-Count",
        ),
        partition=PartitionConfig(strategy="pagination"),
        schema="id INT, userId INT",
    )
    df = read_batch(spark_session, config)
    assert df.rdd.getNumPartitions() == 4
    assert _partition_sizes(df) == [30, 30, 30, 10]
    assert sorted(row.id for row in df.collect()) == list(range(1, 101))


def test_pagination_fanout_from_total_pages_header(spark_session):
    path = "/projects/gitlab-org%2Fcli/repository/tags"
    total = int(_expect(f"{GITLAB}{path}", per_page=1).headers["X-Total"])
    config = live_config(
        base_url=GITLAB,
        name="live_gitlab_tags",
        path=path,
        pagination=PaginationConfig(
            type="page",
            page_param="page",
            limit_param="per_page",
            page_size=100,
            total_pages_header="X-Total-Pages",
        ),
        partition=PartitionConfig(strategy="pagination"),
        schema="name STRING, commit STRUCT<id: STRING, short_id: STRING>",
    )
    df = read_batch(spark_session, config)
    assert df.rdd.getNumPartitions() == math.ceil(total / 100)
    names = [row.name for row in df.collect()]
    assert len(names) == len(set(names)) == total


def test_endpoint_partitions_read_each_path_separately(spark_session):
    config = live_config(
        base_url=JSONPLACEHOLDER,
        name="live_endpoints",
        path="/",
        params={"_limit": 4},
        partition=PartitionConfig(
            strategy="endpoints",
            endpoints=("posts:/posts", "/comments", "users:/users"),
        ),
        schema="id INT, title STRING, email STRING, username STRING",
    )
    df = read_batch(spark_session, config)
    assert _partition_sizes(df) == [4, 4, 4]
    rows = df.collect()
    assert sum(row.title is not None for row in rows) == 4  # posts
    assert sum(row.email is not None for row in rows) == 8  # comments + users
    assert sum(row.username is not None for row in rows) == 4  # users


def test_param_range_partitions_send_one_value_each(spark_session):
    config = live_config(
        base_url=JSONPLACEHOLDER,
        name="live_posts_by_user",
        path="/posts",
        partition=PartitionConfig(
            strategy="param_range",
            param="userId",
            range_start=1,
            range_end=3,
            range_step=1,
            range_kind="numeric",
        ),
        schema="id INT, userId INT",
    )
    df = read_batch(spark_session, config)
    assert _partition_sizes(df) == [10, 10, 10]
    per_partition = (
        df.rdd.glom().map(lambda rows: {row.userId for row in rows}).collect()
    )
    assert per_partition == [{1}, {2}, {3}]


# --- authentication, headers, params (httpbin echoes the request back) ---------


def test_bearer_token_is_sent(spark_session):
    config = live_config(
        base_url=HTTPBIN,
        name="live_bearer",
        path="/bearer",
        auth=AuthConfig(type="bearer"),
        schema="authenticated BOOLEAN, token STRING",
    )
    row = read_batch(spark_session, config, API_TOKEN="live-bearer-token").collect()[0]
    assert row.authenticated is True
    assert row.token == "live-bearer-token"


def test_api_key_header_and_static_headers_are_sent(spark_session):
    config = live_config(
        base_url=HTTPBIN,
        name="live_api_key_header",
        path="/headers",
        auth=AuthConfig(type="api_key", api_key_in="header", api_key_name="X-Api-Key"),
        headers={"X-Polymo-Suite": "live"},
        schema="headers MAP<STRING, STRING>",
    )
    row = read_batch(spark_session, config, API_KEY="live-key").collect()[0]
    assert row.headers["X-Api-Key"] == "live-key"
    assert row.headers["X-Polymo-Suite"] == "live"
    assert row.headers["User-Agent"] == USER_AGENT


def test_api_key_query_param_and_static_params_are_sent(spark_session):
    config = live_config(
        base_url=HTTPBIN,
        name="live_api_key_query",
        path="/get",
        params={"kind": "post", "page_size": 5},
        auth=AuthConfig(type="api_key", api_key_in="query", api_key_name="api_key"),
        schema="args MAP<STRING, STRING>, url STRING",
    )
    row = read_batch(spark_session, config, API_KEY="live-key").collect()[0]
    assert row.args == {"api_key": "live-key", "kind": "post", "page_size": "5"}


def test_oauth2_client_credentials_token_is_fetched_then_sent(spark_session):
    config = live_config(
        base_url=HTTPBIN,
        name="live_oauth2",
        path="/bearer",
        auth=AuthConfig(
            type="oauth2",
            token_url=f"{HTTPBIN}/response-headers?access_token=live-oauth-token",
            client_id="polymo-live",
            scope=("read",),
            audience="https://example.test",
            extra_params={"resource": "posts"},
        ),
        schema="authenticated BOOLEAN, token STRING",
    )
    row = read_batch(spark_session, config, CLIENT_SECRET="live-secret").collect()[0]
    assert row.authenticated is True
    assert row.token == "live-oauth-token"


def test_option_placeholders_are_baked_in_or_left_as_constants(spark_session):
    config = live_config(
        base_url=HTTPBIN,
        name="live_options",
        path="/anything/{resource}",
        params={"resource": "widgets", "q": "{{ options.q }}"},
        headers={"X-Tenant": "{{ options.tenant }}"},
        options={"q": "spark"},
        schema="url STRING, args MAP<STRING, STRING>, headers MAP<STRING, STRING>",
    )
    script = generate(config)
    assert 'PATH: str = "/anything/widgets"' in script
    assert 'PARAMS: dict[str, Any] = {"q": "spark"}' in script
    assert 'OPT_TENANT: str = "REPLACE_ME"' in script
    row = read_batch(spark_session, config, OPT_TENANT="acme").collect()[0]
    assert row.url == f"{HTTPBIN}/anything/widgets?q=spark"
    assert row.args == {"q": "spark"}
    assert row.headers["X-Tenant"] == "acme"


# --- filter pushdown ----------------------------------------------------------


def test_filter_pushdown_sends_equality_filter_as_query_param(spark_session):
    # The record *is* httpbin's echo of the query string, so a `status`
    # column can only hold what the script actually sent. Spark trusts the
    # pushed EqualTo (it is not re-evaluated after the scan) but keeps the
    # implied IS NOT NULL check, so a filter that never reached the API would
    # echo `{}` and the row would be dropped, failing the assertion below.
    config = live_config(
        base_url=HTTPBIN,
        name="live_pushdown",
        path="/anything",
        pushdown_params={"status": "status"},
        record_selector=RecordSelectorConfig(field_path=["args"]),
        schema="status STRING",
    )
    df = read_batch(spark_session, config)
    assert spark_session.conf.get("spark.sql.python.filterPushdown.enabled") == "true"
    pushed = df.filter(col("status") == "active").collect()
    assert [row.status for row in pushed] == ["active"]
    # Without a filter nothing is pushed and the echo is empty. Read through
    # a fresh `load()`: Spark 4.2 keeps the reader that accepted the first
    # pushdown on the DataFrame object, so an unfiltered query on `df`
    # itself would still send `status=active`.
    fresh = spark_session.read.format(registered_format(generate(config))).load()
    assert [row.status for row in fresh.collect()] == [None]


# --- incremental sync ---------------------------------------------------------


def test_incremental_cursor_is_persisted_and_sent_on_the_next_run(
    spark_session, tmp_path
):
    auth, placeholders = github_auth()
    state_file = tmp_path / "state" / "commits.json"
    config = live_config(
        base_url=GITHUB,
        name="live_commits",
        path="/repos/dan1elt0m/polymo/commits",
        params={"per_page": 5},
        auth=auth,
        incremental=IncrementalConfig(
            mode="committer_date",
            cursor_param="since",
            cursor_field="commit.committer.date",
            state_path=str(state_file),
            start_value="2026-08-01T00:00:00Z",
        ),
        schema="sha STRING, commit STRUCT<committer: STRUCT<date: STRING>>",
    )
    first = read_batch(spark_session, config, **placeholders).collect()
    assert 1 <= len(first) <= 5
    dates = [row.commit.committer.date for row in first]
    assert min(dates) >= "2026-08-01T00:00:00Z"

    entry = json.loads(state_file.read_text())["streams"][f"live_commits@{GITHUB}"]
    assert entry["cursor_value"] == max(dates)
    assert (entry["cursor_param"], entry["cursor_field"]) == (
        "since",
        "commit.committer.date",
    )
    assert entry["mode"] == "committer_date"

    # a fresh run reads the stored cursor and asks GitHub for `since=<max>`
    second = read_batch(spark_session, config, **placeholders).collect()
    assert second
    assert all(row.commit.committer.date >= max(dates) for row in second)


# --- XML ----------------------------------------------------------------------


def test_xml_attributes_with_namespaced_record_path(spark_session):
    config = live_config(
        base_url=ECB,
        name="live_ecb_rates",
        path="/stats/eurofxref/eurofxref-daily.xml",
        response_format="xml",
        xml_record_path=f".//{EUROFXREF}Cube[@currency]",
        record_selector=RecordSelectorConfig(cast_to_schema_types=True),
        schema="`@currency` STRING, `@rate` DOUBLE",
    )
    rows = read_batch(spark_session, config).collect()
    rates = {row["@currency"]: row["@rate"] for row in rows}
    assert len(rates) > 20
    assert isinstance(rates["USD"], float) and rates["USD"] > 0


def test_xml_child_elements_become_columns(spark_session):
    config = live_config(
        base_url=ARXIV,
        name="live_arxiv",
        path="/api/query",
        params={"search_query": 'ti:"delta lake"', "max_results": 5},
        response_format="xml",
        xml_record_path=f".//{ATOM}entry",
        schema="id STRING, title STRING, published STRING",
    )
    rows = read_batch(spark_session, config).collect()
    assert rows
    for row in rows:
        assert row.id.startswith("http://arxiv.org/abs/")
        assert "Delta Lake" in row.title
        assert row.published.endswith("Z")


# --- error handling -----------------------------------------------------------


def test_retries_5xx_with_backoff_then_surfaces_the_error(spark_session):
    config = live_config(
        base_url=HTTPBIN,
        name="live_server_error",
        path="/status/500",
        error_handler=ErrorHandlerConfig(
            max_retries=2,
            retry_statuses=("5XX",),
            backoff=BackoffConfig(initial_delay_seconds=1.0, max_delay_seconds=1.0),
        ),
        schema="code INT",
    )
    started = time.monotonic()
    with pytest.raises(Exception, match="500 Server Error"):
        read_batch(spark_session, config).collect()
    assert time.monotonic() - started >= 2.0  # two 1s backoff sleeps


def test_no_retries_fails_on_the_first_error(spark_session):
    config = live_config(
        base_url=HTTPBIN,
        name="live_not_found",
        path="/status/404",
        error_handler=ErrorHandlerConfig(max_retries=0),
        schema="code INT",
    )
    assert "_should_retry" not in generate(config)
    with pytest.raises(Exception, match="404 Client Error"):
        read_batch(spark_session, config).collect()


# --- streaming ----------------------------------------------------------------


def test_streaming_table_reads_one_page_per_micro_batch(spark_session, tmp_path):
    config = live_config(
        base_url=JSONPLACEHOLDER,
        name="live_posts_stream",
        path="/posts",
        streaming=True,
        pagination=PaginationConfig(
            type="page", page_param="_page", limit_param="_limit", page_size=40
        ),
        schema="id INT, userId INT, title STRING",
    )
    script = generate(config)
    exec_script(script)
    stream = spark_session.readStream.format(registered_format(script)).load()
    query = (
        stream.writeStream.format("memory")
        .queryName("live_posts_stream")
        .trigger(processingTime="200 milliseconds")
        .option("checkpointLocation", str(tmp_path / "checkpoint"))
        .start()
    )
    try:
        deadline = time.monotonic() + 120
        while time.monotonic() < deadline:
            if spark_session.table("live_posts_stream").count() >= 100:
                break
            time.sleep(1)
        rows = spark_session.table("live_posts_stream").collect()
    finally:
        query.stop()
    assert sorted(row.id for row in rows) == list(range(1, 101))
    assert all(row.title for row in rows)


# --- bundle project -----------------------------------------------------------


def test_bundle_project_reads_through_spark_from_the_packaged_source(
    spark_session, tmp_path
):
    config = live_config(
        base_url=JSONPLACEHOLDER,
        name="posts",
        path="/posts",
        params={"_limit": 7},
        schema="id INT, title STRING",
    )
    files = generate_bundle(
        config, project_name="live_bundle_demo", catalog="main", schema="raw"
    )
    project = tmp_path / "project"
    for relpath, content in files.items():
        target = project / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
    # the wheel Databricks installs, stood in for by a zip on every worker's
    # sys.path: the DataSource class is pickled by reference and re-imported
    archive = shutil.make_archive(
        str(tmp_path / "live_bundle_demo"), "zip", root_dir=project / "src"
    )
    spark_session.sparkContext.addPyFile(archive)

    namespace = exec_script(files["pipelines/posts.py"])
    df = spark_session.read.format("posts_source").load()
    assert [row.id for row in df.collect()] == list(range(1, 8))
    assert namespace["posts"]().count() == 7
