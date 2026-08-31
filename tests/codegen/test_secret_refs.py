"""Databricks secret-scope references in generated code.

`AuthConfig.secret` (bearer/api_key/oauth2) and `StreamConfig.option_secrets`
(OPT_* placeholders) swap the usual `"REPLACE_ME"` placeholder assignment for
a call to a generated `_dbx_secret(scope, key)` helper — driver-side
`dbutils.secrets.get`, with a clear RuntimeError outside Databricks. The
helper is emitted exactly once, only when at least one slot references a
secret; configs with no secret refs at all must be byte-for-byte unaffected
(covered by the existing golden tests).
"""

from __future__ import annotations

from polymo.codegen import generate_core
from polymo.config import AuthConfig, SecretRef
from tests.codegen.helpers import assert_hygiene, make_config

_HELPER_SIGNATURE = "def _dbx_secret(scope: str, key: str) -> str:"


def test_bearer_secret_ref_emits_dbx_secret_call():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="bearer", secret=SecretRef(scope="my-scope", key="my-key")
        ),
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'API_TOKEN: str = _dbx_secret("my-scope", "my-key")' in core
    assert 'API_TOKEN: str = "REPLACE_ME"' not in core
    assert core.count(_HELPER_SIGNATURE) == 1


def test_api_key_secret_ref_emits_dbx_secret_call():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="api_key",
            api_key_in="header",
            api_key_name="X-API-Key",
            secret=SecretRef(scope="kv-scope", key="api-key"),
        ),
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'API_KEY: str = _dbx_secret("kv-scope", "api-key")' in core
    assert core.count(_HELPER_SIGNATURE) == 1


def test_oauth2_secret_ref_emits_dbx_secret_call():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(
            type="oauth2",
            token_url="https://x/token",
            client_id="cid",
            secret=SecretRef(scope="kv-scope", key="client-secret"),
        ),
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'CLIENT_SECRET: str = _dbx_secret("kv-scope", "client-secret")' in core
    assert core.count(_HELPER_SIGNATURE) == 1


def test_option_secret_ref_emits_dbx_secret_call():
    config = make_config(
        base_url="https://x",
        headers={"Authorization": "Basic {{ options.api_key_b64 }}"},
        option_secrets={"api_key_b64": SecretRef(scope="opt-scope", key="opt-key")},
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert 'OPT_API_KEY_B64: str = _dbx_secret("opt-scope", "opt-key")' in core
    assert core.count(_HELPER_SIGNATURE) == 1


def test_helper_emitted_once_when_multiple_slots_reference_secrets():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="bearer", secret=SecretRef(scope="s1", key="k1")),
        headers={"X-Tenant": "{{ options.tenant_id }}"},
        option_secrets={"tenant_id": SecretRef(scope="s2", key="k2")},
    )
    core = generate_core(config)
    assert_hygiene(core)
    assert core.count(_HELPER_SIGNATURE) == 1
    assert 'API_TOKEN: str = _dbx_secret("s1", "k1")' in core
    assert 'OPT_TENANT_ID: str = _dbx_secret("s2", "k2")' in core


def test_helper_not_emitted_when_no_secret_refs():
    config = make_config(base_url="https://x", auth=AuthConfig(type="bearer"))
    core = generate_core(config)
    assert_hygiene(core)
    assert "_dbx_secret" not in core
    assert 'API_TOKEN: str = "REPLACE_ME"' in core


def test_helper_body_matches_spec_exactly():
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="bearer", secret=SecretRef(scope="s", key="k")),
    )
    core = generate_core(config)
    assert_hygiene(core)
    expected = '''def _dbx_secret(scope: str, key: str) -> str:
    """Resolve a Databricks secret on the driver."""
    try:
        from pyspark.dbutils import DBUtils  # type: ignore[import]
        from pyspark.sql import SparkSession

        session = SparkSession.getActiveSession()
        if session is None:
            raise RuntimeError("no active Spark session")
        return DBUtils(session).secrets.get(scope, key)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"could not resolve Databricks secret {scope}/{key}: {exc}. "
            "Outside Databricks, replace this call with the literal value."
        ) from exc'''
    assert expected in core


def test_dbx_secret_import_is_guarded_inside_function_not_top_level():
    """Codegen output must stay pyspark-import-free at module scope for
    preview to keep working even without pyspark installed — the helper's
    `pyspark` imports must be local to the function body."""
    config = make_config(
        base_url="https://x",
        auth=AuthConfig(type="bearer", secret=SecretRef(scope="s", key="k")),
    )
    core = generate_core(config)
    top_level_lines = [
        line
        for line in core.splitlines()
        if line.startswith("import ") or line.startswith("from ")
    ]
    assert not any("pyspark" in line for line in top_level_lines)
