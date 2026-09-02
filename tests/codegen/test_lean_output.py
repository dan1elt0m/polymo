"""Generated output stays comment-free and tool-reference-free.

Covers items from the "lean generated code" cleanup: every generated `.py`
file (single-file scripts and bundle projects alike) should read like
hand-written code — no explanatory `#` comments beyond the couple of
hygiene pragmas that are genuinely load-bearing, and no mention of the
`polymo` tool name anywhere in the content a user would actually read.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from polymo.codegen import generate, generate_core
from polymo.codegen.bundle import generate_bundle
from polymo.config import (
    AuthConfig,
    IncrementalConfig,
    PaginationConfig,
    PartitionConfig,
    SecretRef,
    UcSecretRef,
)
from tests.codegen.helpers import make_config

GOLDEN_DIR = Path(__file__).parent / "golden"
GOLDEN_BUNDLE_DIR = Path(__file__).parent / "golden_bundle"

# A trailing `#`-comment is allowed only when it's one of these two hygiene
# pragmas — everything else must be gone from generated output.
_ALLOWED_TRAILING_COMMENT_RE = re.compile(r"#\s*(noqa\b|type:\s*ignore\b)")

# A config flag interpolated straight into a runtime condition ("if not
# True or ...", "30.0 > 0") reads as generated, not hand-written — the
# generator is supposed to specialize on the flag's value at generation
# time instead. `\b\d+(\.\d+)?\s*[<>]=?\s*\d` catches a numeric-literal
# comparison like `30.0 > 0`; it deliberately requires a digit on *both*
# sides so real runtime comparisons against a variable (`status <= 599`,
# `page >= int(total)`) don't trip it.
_LITERAL_CONDITION_RE = re.compile(
    r"\bnot True\b|\bnot False\b|\bif True\b|\bif False\b|\bor False\b|\band True\b"
    r"|\b\d+(?:\.\d+)?\s*[<>]=?\s*\d"
)


def _assert_no_literal_conditions(code: str, label: str) -> None:
    for lineno, line in enumerate(code.splitlines(), start=1):
        match = _LITERAL_CONDITION_RE.search(line)
        if match:
            pytest.fail(
                f"{label}:{lineno}: literal interpolated into a condition"
                f" ({match.group(0)!r}) — specialize it at generation time"
                f" instead: {line!r}"
            )


def _assert_no_stray_comments(code: str, label: str) -> None:
    for lineno, line in enumerate(code.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            pytest.fail(f"{label}:{lineno}: full-line comment: {line!r}")
        hash_index = line.find("#")
        if hash_index == -1:
            continue
        # A `#` can legitimately appear inside a string literal (e.g. a
        # retry-status literal or an escaped value) — only flag one that
        # isn't a hygiene pragma AND isn't preceded by an odd number of
        # quote characters (a cheap but effective proxy: for every case
        # actually emitted by the templates, a `#` that starts a real
        # trailing comment is preceded only by code, never by an unclosed
        # string).
        trailing = line[hash_index:]
        if _ALLOWED_TRAILING_COMMENT_RE.match(trailing):
            continue
        # Strings containing a literal `#` (e.g. `_should_retry`'s "5XX"
        # docs or an escaped config value) are the only other source of a
        # `#` mid-line; skip a `#` that sits inside a quoted literal by
        # checking for balanced quotes before it.
        before = line[:hash_index]
        if before.count('"') % 2 == 1 or before.count("'") % 2 == 1:
            continue
        pytest.fail(f"{label}:{lineno}: trailing comment: {line!r}")


def _assert_no_polymo_mentions(content: str, label: str) -> None:
    lowered = content.lower()
    if "polymo" in lowered:
        idx = lowered.index("polymo")
        window = content[max(0, idx - 40) : idx + 40]
        pytest.fail(f"{label}: contains 'polymo': ...{window}...")


# --- golden fixtures: exact bytes already on disk ----------------------------


def _all_golden_py_files():
    paths = []
    if GOLDEN_DIR.exists():
        paths.extend(sorted(GOLDEN_DIR.glob("*.py")))
    if GOLDEN_BUNDLE_DIR.exists():
        paths.extend(sorted(GOLDEN_BUNDLE_DIR.rglob("*.py")))
    return paths


@pytest.mark.parametrize("path", _all_golden_py_files(), ids=lambda p: p.name)
def test_golden_py_files_have_no_stray_comments(path: Path):
    _assert_no_stray_comments(path.read_text(), str(path))


@pytest.mark.parametrize("path", _all_golden_py_files(), ids=lambda p: p.name)
def test_golden_py_files_have_no_literal_conditions(path: Path):
    _assert_no_literal_conditions(path.read_text(), str(path))


def test_golden_bundle_files_have_no_polymo_mentions():
    for path in GOLDEN_BUNDLE_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.name == ".polymo-bundle.json":
            # explicit exception: the tool's own manifest, read back by the
            # "Run on Databricks" flow — its `generated_by` field is allowed
            # (and expected) to name polymo.
            continue
        _assert_no_polymo_mentions(path.read_text(), str(path))


def test_golden_single_file_scripts_have_no_polymo_mentions():
    for path in GOLDEN_DIR.glob("*.py"):
        _assert_no_polymo_mentions(path.read_text(), str(path))


# --- broader sweep: configs not necessarily covered by a golden --------------
# Comments/docstrings are conditional on config shape (secret refs, OPT_*
# placeholders, windows, incremental state, streaming, oauth2, ...), so the
# golden fixtures alone don't exercise every branch. This sweep generates a
# battery of representative configs directly and re-checks them.

SWEEP_CONFIGS = {
    "plain": make_config(base_url="https://x"),
    "bearer_secret": make_config(
        base_url="https://x",
        auth=AuthConfig(type="bearer", secret=SecretRef(scope="s", key="k")),
    ),
    "api_key_query_secret": make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="api_key",
            api_key_in="query",
            api_key_name="key",
            secret=SecretRef(scope="s", key="k"),
        ),
    ),
    "oauth2_uc_secret": make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="oauth2",
            token_url="https://x/token",
            client_id="cid",
            uc_secret=UcSecretRef(
                credential="cred", vault_url="https://v/", secret_name="s"
            ),
        ),
    ),
    "windowed_incremental": make_config(
        base_url="https://x",
        partition=PartitionConfig(strategy="endpoints", endpoints=("/a", "/b")),
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
        schema="id INT, updated STRING",
    ),
    "incremental_remote_state": make_config(
        base_url="https://x",
        incremental=IncrementalConfig(
            mode="cursor",
            cursor_param="since",
            cursor_field="meta.updated",
            state_path="s3://team/state/posts.json",
            start_value="2024-01-01T00:00:00Z",
            state_key="posts-prod",
        ),
    ),
    "pagination_fanout": make_config(
        base_url="https://x",
        pagination=PaginationConfig(
            type="page",
            page_param="page",
            limit_param="per_page",
            page_size=100,
            total_pages_path=("meta", "pages"),
            total_pages_header="X-Pages",
            total_records_path=("meta", "total"),
            total_records_header="X-Total",
        ),
        partition=PartitionConfig(strategy="pagination"),
        schema="id BIGINT",
    ),
    "pagination_fanout_offset_incremental": make_config(
        base_url="https://x",
        pagination=PaginationConfig(
            type="offset",
            offset_param="offset",
            limit_param="limit",
            page_size=50,
            start_offset=100,
            total_records_header="X-Total",
        ),
        partition=PartitionConfig(strategy="pagination"),
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
    ),
    "pushdown": make_config(
        base_url="https://x",
        params={"status": "open"},
        pushdown_params={"status": "status", "owner_id": "owner"},
        schema="id BIGINT, status STRING",
    ),
    "pushdown_fanout_incremental_windows": make_config(
        base_url="https://x",
        partition=PartitionConfig(strategy="param_range", param="region", values="a,b"),
        incremental=IncrementalConfig(
            mode="cursor", cursor_param="since", cursor_field="updated"
        ),
        pushdown_params={"status": "status"},
    ),
    "streaming": make_config(
        base_url="https://x",
        streaming=True,
        schema="id BIGINT",
        pagination=PaginationConfig(type="page", page_param="page", page_size=100),
    ),
    "option_placeholder": make_config(
        base_url="https://x",
        headers={"Authorization": "Basic {{ options.api_key_b64 }}"},
    ),
    "option_placeholder_secret": make_config(
        base_url="https://x",
        headers={"X-Tenant": "{{ options.tenant_id }}"},
        option_secrets={"tenant_id": SecretRef(scope="s", key="tenant")},
    ),
    "xml": make_config(
        base_url="https://x", response_format="xml", xml_record_path=".//item"
    ),
}


@pytest.mark.parametrize("case", SWEEP_CONFIGS)
def test_single_file_sweep_has_no_stray_comments_or_polymo_mentions(case):
    script = generate(SWEEP_CONFIGS[case])
    _assert_no_stray_comments(script, f"generate({case})")
    _assert_no_polymo_mentions(script, f"generate({case})")
    _assert_no_literal_conditions(script, f"generate({case})")


@pytest.mark.parametrize("case", SWEEP_CONFIGS)
def test_core_sweep_has_no_stray_comments_or_polymo_mentions(case):
    core = generate_core(SWEEP_CONFIGS[case])
    _assert_no_stray_comments(core, f"generate_core({case})")
    _assert_no_polymo_mentions(core, f"generate_core({case})")
    _assert_no_literal_conditions(core, f"generate_core({case})")


@pytest.mark.parametrize("case", SWEEP_CONFIGS)
def test_bundle_sweep_has_no_stray_comments_or_polymo_mentions(case):
    files = generate_bundle(
        SWEEP_CONFIGS[case], project_name=f"sweep_{case}", catalog="main", schema="raw"
    )
    for relpath, content in files.items():
        if relpath.endswith(".py"):
            _assert_no_stray_comments(content, f"bundle({case})/{relpath}")
            _assert_no_literal_conditions(content, f"bundle({case})/{relpath}")
        if relpath == ".polymo-bundle.json":
            continue
        _assert_no_polymo_mentions(content, f"bundle({case})/{relpath}")


def test_manifest_keeps_the_one_allowed_polymo_mention():
    files = generate_bundle(
        make_config(base_url="https://x"),
        project_name="demo",
        catalog="main",
        schema="raw",
    )
    assert "polymo" in files[".polymo-bundle.json"].lower()
