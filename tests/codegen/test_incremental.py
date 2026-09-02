"""Incremental cursor state in generated scripts.

Restores the 0.x `_IncrementalTracker` semantics as generated code: a state
file at `stream.incremental.state_path` (local path or fsspec URL, default
`<stream>_state.json`), keyed by `state_key` (default `<stream>@<base_url>`),
seeded from `start_value` when nothing is stored, applied as a query param
via `setdefault` (an explicit param wins), and committed per partition with
a monotone write (a lower value never overwrites a higher one).
"""

from __future__ import annotations

import json
import sys

import pytest

from polymo.codegen import generate, generate_core
from polymo.config import IncrementalConfig, PartitionConfig
from tests.codegen.helpers import (
    fake_schema,
    make_config,
    run_generated,
    run_generated_script,
)


def _incremental(**overrides):
    fields = dict(mode="updated_at", cursor_param="since", cursor_field="updated")
    fields.update(overrides)
    return IncrementalConfig(**fields)


def _echo_since(http_server, seen: list):
    """Route that records the `since` param and returns two rows."""

    def route(query, headers, body):
        seen.append(query.get("since"))
        return (
            200,
            [{"id": 1, "updated": "2026-01-01"}, {"id": 2, "updated": "2026-02-01"}],
            {},
        )

    http_server.routes["/posts"] = route


def _read_partition(module, partition=None) -> list:
    """Drive the generated `_Reader.read()` exactly as an executor would."""
    reader = module._Reader(fake_schema("id", "updated"))
    return list(reader.read(partition))


def test_reader_commits_partition_max_to_state_file(http_server, tmp_path):
    seen: list = []
    _echo_since(http_server, seen)
    state_file = tmp_path / "nested" / "dir" / "state.json"
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path=str(state_file)),
        schema="id BIGINT, updated STRING",
    )
    module = run_generated_script(config)

    rows = _read_partition(module)

    assert rows == [(1, "2026-01-01"), (2, "2026-02-01")]
    assert seen == [None]
    # parent directories are created, the write is atomic (no .tmp left
    # behind) and the document has the 0.x shape, keyed by <stream>@<base_url>
    assert state_file.exists()
    assert not state_file.with_suffix(".json.tmp").exists()
    document = json.loads(state_file.read_text())
    key = f"posts@{http_server.url}"
    assert set(document) == {"streams"}
    entry = document["streams"][key]
    assert entry["cursor_param"] == "since"
    assert entry["cursor_field"] == "updated"
    assert entry["cursor_value"] == "2026-02-01"
    assert entry["mode"] == "updated_at"
    assert entry["updated_at"].endswith("Z")

    # the next run sends the stored cursor
    _read_partition(run_generated_script(config))
    assert seen == [None, "2026-02-01"]


def test_reader_skips_write_when_no_cursor_observed(http_server, tmp_path):
    http_server.routes["/posts"] = lambda q, h, b: (200, [{"id": 1}], {})
    state_file = tmp_path / "state.json"
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path=str(state_file)),
        schema="id BIGINT, updated STRING",
    )
    _read_partition(run_generated_script(config))
    assert not state_file.exists()


def test_default_state_path_is_stream_state_json_next_to_script():
    config = make_config(base_url="https://x", incremental=_incremental())
    script = generate_core(config)
    assert 'STATE_PATH: str = "posts_state.json"' in script
    assert 'STATE_KEY: str = "posts@https://x"' in script
    assert "START_VALUE: str | None = None" in script


def test_start_value_seeds_only_when_nothing_is_stored(http_server, tmp_path):
    seen: list = []
    _echo_since(http_server, seen)
    state_file = tmp_path / "state.json"
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path=str(state_file), start_value="2025-12-31"),
        schema="id BIGINT, updated STRING",
    )
    module = run_generated_script(config)
    assert 'START_VALUE: str | None = "2025-12-31"' in generate_core(config)

    _read_partition(module)
    assert seen == ["2025-12-31"]

    _read_partition(module)
    assert seen == ["2025-12-31", "2026-02-01"]


def test_start_value_is_never_written_back_when_nothing_newer_is_seen(
    http_server, tmp_path
):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [{"id": 1, "updated": "2024-01-01"}],
        {},
    )
    state_file = tmp_path / "state.json"
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path=str(state_file), start_value="2025-01-01"),
        schema="id BIGINT, updated STRING",
    )
    _read_partition(run_generated_script(config))
    # the observed max (2024) is below the seed (2025): nothing to persist
    assert not state_file.exists()


def test_custom_state_key(http_server, tmp_path):
    seen: list = []
    _echo_since(http_server, seen)
    state_file = tmp_path / "state.json"
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path=str(state_file), state_key="posts-prod"),
        schema="id BIGINT, updated STRING",
    )
    module = run_generated_script(config)
    _read_partition(module)
    document = json.loads(state_file.read_text())
    assert list(document["streams"]) == ["posts-prod"]


@pytest.mark.parametrize(
    "document",
    [
        {"streams": {"posts@BASE": {"cursor_value": "2026-02-01", "mode": "x"}}},
        {"streams": {"posts@BASE": {"value": "2026-02-01"}}},
        {"posts@BASE": {"cursor_value": "2026-02-01"}},
        {"posts@BASE": "2026-02-01"},
    ],
    ids=["streams-entry", "legacy-value-key", "flat-entry", "flat-scalar"],
)
def test_reads_lenient_0x_state_document_shapes(http_server, tmp_path, document):
    seen: list = []
    _echo_since(http_server, seen)
    state_file = tmp_path / "state.json"
    text = json.dumps(document).replace("BASE", http_server.url)
    state_file.write_text(text)
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path=str(state_file)),
    )
    module = run_generated(config)
    assert module._read_state() == "2026-02-01"
    list(module.fetch_records())
    assert seen == ["2026-02-01"]


@pytest.mark.parametrize("text", ["", "{not json", "[1, 2]", '{"streams": 3}'])
def test_unreadable_state_document_means_no_cursor(http_server, tmp_path, text):
    seen: list = []
    _echo_since(http_server, seen)
    state_file = tmp_path / "state.json"
    state_file.write_text(text)
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path=str(state_file)),
    )
    module = run_generated(config)
    assert module._read_state() is None
    list(module.fetch_records())
    assert seen == [None]


def test_write_state_is_monotone(tmp_path):
    state_file = tmp_path / "state.json"
    config = make_config(
        base_url="https://x", incremental=_incremental(state_path=str(state_file))
    )
    module = run_generated(config)

    module._write_state("2026-03-01")
    module._write_state("2026-01-01")
    assert module._read_state() == "2026-03-01"

    module._write_state("2026-05-01")
    assert module._read_state() == "2026-05-01"


def test_write_state_merges_into_existing_document(tmp_path):
    state_file = tmp_path / "state.json"
    state_file.write_text(
        json.dumps({"streams": {"other@https://y": {"cursor_value": "keep"}}})
    )
    config = make_config(
        base_url="https://x", incremental=_incremental(state_path=str(state_file))
    )
    module = run_generated(config)
    module._write_state("2026-03-01")
    document = json.loads(state_file.read_text())
    assert document["streams"]["other@https://y"] == {"cursor_value": "keep"}
    assert document["streams"]["posts@https://x"]["cursor_value"] == "2026-03-01"


def test_explicit_param_wins_over_stored_cursor(http_server, tmp_path):
    seen: list = []
    _echo_since(http_server, seen)
    state_file = tmp_path / "state.json"
    config = make_config(
        base_url=http_server.url,
        params={"since": "pinned"},
        incremental=_incremental(state_path=str(state_file)),
    )
    module = run_generated(config)
    module._write_state("2026-03-01")
    list(module.fetch_records())
    assert seen == ["pinned"]


def test_dotted_cursor_field_walks_nested_records(http_server, tmp_path):
    http_server.routes["/posts"] = lambda q, h, b: (
        200,
        [
            {"id": 1, "meta": {"updated": "2026-01-01"}},
            {"id": 2, "meta": {"updated": "2026-02-01"}},
            {"id": 3, "meta": "not a dict"},
            {"id": 4},
        ],
        {},
    )
    state_file = tmp_path / "state.json"
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(
            cursor_field="meta.updated", state_path=str(state_file)
        ),
        schema="id BIGINT",
    )
    module = run_generated_script(config)
    assert module._cursor_of({"meta": {"updated": 7}}) == "7"
    assert module._cursor_of({"meta": None}) is None
    _read_partition(module)
    assert module._read_state() == "2026-02-01"


def test_cursor_values_are_compared_as_strings(tmp_path):
    state_file = tmp_path / "state.json"
    config = make_config(
        base_url="https://x", incremental=_incremental(state_path=str(state_file))
    )
    module = run_generated(config)
    assert module._cursor_of({"updated": 42}) == "42"
    module._write_state("9")
    module._write_state("10")
    assert module._read_state() == "9"


def test_windowed_partitions_commit_the_global_max(http_server, tmp_path):
    http_server.routes["/a"] = lambda q, h, b: (200, [{"updated": "2026-05-01"}], {})
    http_server.routes["/b"] = lambda q, h, b: (200, [{"updated": "2026-02-01"}], {})
    state_file = tmp_path / "state.json"
    config = make_config(
        base_url=http_server.url,
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
        incremental=_incremental(state_path=str(state_file)),
        schema="updated STRING",
    )
    module = run_generated_script(config)
    reader = module._Reader(fake_schema("updated"))
    partitions = reader.partitions()
    assert [p.value for p in partitions] == [0, 1]
    # whichever order the executors finish in, the stored cursor is the max
    for partition in partitions:
        list(reader.read(partition))
    assert module._read_state() == "2026-05-01"


# --- remote (fsspec) state paths ---------------------------------------------


def test_local_state_path_generates_no_fsspec_code():
    for state_path in (None, "/Volumes/main/raw/state.json", "file:///tmp/s.json"):
        config = make_config(
            base_url="https://x", incremental=_incremental(state_path=state_path)
        )
        script = generate(config)
        assert "fsspec" not in script
        assert "_state_fs" not in script
        assert "os.replace(tmp_path, STATE_PATH)" in script


def test_file_url_state_path_is_emitted_as_a_plain_path():
    config = make_config(
        base_url="https://x",
        incremental=_incremental(state_path="file:///tmp/posts/state.json"),
    )
    assert 'STATE_PATH: str = "/tmp/posts/state.json"' in generate_core(config)


@pytest.mark.parametrize(
    "state_path",
    [
        "s3://team/state.json",
        "gs://team/state.json",
        "abfss://c@a.dfs.core.windows.net/s.json",
        "dbfs:/state.json",
    ],
)
def test_remote_state_path_generates_fsspec_branch(state_path):
    config = make_config(
        base_url="https://x", incremental=_incremental(state_path=state_path)
    )
    script = generate(config)
    assert "def _state_fs() -> tuple[Any, str]:" in script
    assert "import fsspec" in script
    assert "fsspec.core.url_to_fs(STATE_PATH)" in script
    assert "fs.makedirs(directory, exist_ok=True)" in script
    assert "os.replace(" not in script


def test_remote_state_path_raises_clear_error_without_fsspec(monkeypatch):
    config = make_config(
        base_url="https://x",
        incremental=_incremental(state_path="s3://team/state.json"),
    )
    module = run_generated(config)
    monkeypatch.setitem(sys.modules, "fsspec", None)
    with pytest.raises(RuntimeError) as excinfo:
        module._read_state()
    assert "fsspec is required to use non-local incremental_state_path values" in str(
        excinfo.value
    )


def test_remote_state_path_round_trips_through_fsspec(http_server):
    fsspec = pytest.importorskip("fsspec")
    seen: list = []
    _echo_since(http_server, seen)
    config = make_config(
        base_url=http_server.url,
        incremental=_incremental(state_path="memory://state/nested/posts.json"),
        schema="id BIGINT, updated STRING",
    )
    module = run_generated_script(config)
    memory_fs = fsspec.filesystem("memory")
    memory_fs.rm("/state", recursive=True) if memory_fs.exists("/state") else None

    _read_partition(module)
    assert seen == [None]
    assert memory_fs.exists("/state/nested/posts.json")
    with memory_fs.open("/state/nested/posts.json") as fh:
        document = json.load(fh)
    assert (
        document["streams"][f"posts@{http_server.url}"]["cursor_value"] == "2026-02-01"
    )

    _read_partition(module)
    assert seen == [None, "2026-02-01"]

    module._write_state("2026-01-01")
    assert module._read_state() == "2026-02-01"
