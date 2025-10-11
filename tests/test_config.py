from pathlib import Path

import pytest

from polymo.config import (
    ConfigError,
    RestSourceConfig,
    config_to_dict,
    dump_config,
    load_config,
)
from polymo.pydantic_config import (
    PaginationModel,
    PolymoConfig,
)


def write_config(tmp_path: Path, content: str) -> Path:
    config_path = tmp_path / "config.yml"
    config_path.write_text(content)
    return config_path


def test_load_config_success(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        """
version: 0.1
source:
  type: rest
  base_url: https://api.test
stream:
  name: sample
  path: /objects
  infer_schema: true
""".strip(),
    )

    config = load_config(config_path)

    assert isinstance(config, RestSourceConfig)
    assert config.base_url == "https://api.test"
    assert config.auth.type == "none"
    assert config.stream.name == "sample"
    assert config.stream.infer_schema is True
    assert config.stream.error_handler.max_retries == 5
    assert config.stream.error_handler.retry_statuses == ("5XX", "429")


def test_load_config_missing_file(tmp_path: Path) -> None:
    config_path = tmp_path / "missing.yml"

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_invalid_auth_requires_token(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        """
version: 0.1
source:
  type: rest
  base_url: https://api.test
  auth:
    type: bearer
streams:
  - name: bad
    path: /objects
""".strip(),
    )

    with pytest.raises(ConfigError):
        load_config(config_path)


def test_config_to_dict_and_dump(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        """
version: 0.1
source:
  type: rest
  base_url: https://api.test
stream:
  name: sample
  path: /objects
  params:
    limit: 10
""".strip(),
    )

    config = load_config(config_path)
    config_dict = config_to_dict(config)
    assert config_dict["source"]["base_url"] == "https://api.test"
    assert config_dict["stream"]["params"]["limit"] == 10
    assert config_dict["stream"]["record_selector"] == {
        "field_path": [],
        "record_filter": None,
        "cast_to_schema_types": False,
    }
    assert config_dict["stream"]["error_handler"]["max_retries"] == 5

    yaml_text = dump_config(config)
    assert "base_url: https://api.test" in yaml_text
    assert "limit: 10" in yaml_text


def test_record_selector_round_trip(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        """
version: 0.1
source:
  type: rest
  base_url: https://api.test
stream:
  name: sample
  path: /objects
  record_selector:
    field_path:
      - response
      - docs
    record_filter: "{{ record.status == 'active' }}"
    cast_to_schema_types: true
  schema: id INT, status STRING
""".strip(),
    )

    config = load_config(config_path)
    selector = config.stream.record_selector
    assert selector.field_path == ["response", "docs"]
    assert selector.record_filter == "{{ record.status == 'active' }}"
    assert selector.cast_to_schema_types is True


def test_custom_error_handler_round_trip(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        """
version: 0.1
source:
  type: rest
  base_url: https://api.test
stream:
  name: sample
  path: /objects
  error_handler:
    max_retries: 2
    retry_statuses:
      - 404
      - 5XX
    retry_on_timeout: false
    backoff:
      initial_delay_seconds: 0.5
      max_delay_seconds: 4
      multiplier: 1.5
""".strip(),
    )

    config = load_config(config_path)
    handler = config.stream.error_handler
    assert handler.max_retries == 2
    assert handler.retry_statuses == ("404", "5XX")
    assert handler.retry_on_timeout is False
    assert handler.retry_on_connection_errors is True
    assert handler.backoff.initial_delay_seconds == 0.5
    assert handler.backoff.max_delay_seconds == 4.0
    assert handler.backoff.multiplier == 1.5

    config_yaml = dump_config(config)
    assert "error_handler:" in config_yaml


def test_oauth2_auth_uses_runtime_secret(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        """
version: 0.1
source:
  type: rest
  base_url: https://api.oauth
  auth:
    type: oauth2
    token_url: https://auth.example.com/token
    client_id: my-client
    scope:
      - read
      - write
stream:
  name: sample
  path: /resources
""".strip(),
    )

    config = load_config(config_path, options={"oauth_client_secret": "s3cret"})
    assert config.auth.type == "oauth2"
    assert config.auth.token_url == "https://auth.example.com/token"
    assert config.auth.client_id == "my-client"
    assert config.auth.client_secret == "s3cret"
    assert config.auth.scope == ("read", "write")

    config_dict = config_to_dict(config)
    assert config_dict["source"]["auth"]["type"] == "oauth2"


def test_pydantic_model_from_yaml() -> None:
    config_yaml = """
version: 0.1
source:
  type: rest
  base_url: https://api.test
stream:
  name: sample
  path: /objects
  params:
    limit: 5
""".strip()

    model = PolymoConfig.from_yaml(config_yaml)

    rest_config = model.to_rest_config()
    assert rest_config.base_url == "https://api.test"
    assert rest_config.stream.params["limit"] == 5

    reader_config = model.reader_config()
    assert reader_config["source"]["base_url"] == "https://api.test"
    assert reader_config["stream"]["params"]["limit"] == 5


def test_pydantic_model_from_dict_requires_mapping() -> None:
    with pytest.raises(ConfigError):
        PolymoConfig.from_dict(123)  # type: ignore[arg-type]


def test_pydantic_model_manual_build() -> None:
    model = PolymoConfig(
        base_url="https://api.test",
        path="/objects",
        params={"limit": 10},
        pagination=PaginationModel(type="offset", limit_param="limit", page_size=100),
    )

    rest_config = model.to_rest_config()
    assert rest_config.base_url == "https://api.test"
    assert rest_config.stream.params["limit"] == 10
    assert rest_config.stream.pagination.limit_param == "limit"
    assert rest_config.stream.pagination.page_size == 100

    reader_config = model.reader_config()
    assert reader_config["stream"]["pagination"]["type"] == "offset"
    assert reader_config["stream"]["pagination"]["limit_param"] == "limit"


def test_flat_polymo_config_roundtrip() -> None:
    flat = PolymoConfig(
        base_url="https://api.test",
        path="/objects",
        params={"limit": 10},
    )

    rest_config = flat.to_rest_config()
    assert rest_config.base_url == "https://api.test"
    assert rest_config.stream.params["limit"] == 10

    reader_config = flat.reader_config()
    assert reader_config["stream"]["params"]["limit"] == 10

    yaml_text = flat.dump_yaml()
    reloaded = PolymoConfig.from_yaml(yaml_text)
    assert reloaded.base_url == "https://api.test"
    assert reloaded.params["limit"] == 10


def test_oauth2_auth_accepts_secret_wrappers(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        """
version: 0.1
source:
  type: rest
  base_url: https://api.oauth
  auth:
    type: oauth2
    token_url: https://auth.example.com/token
    client_id: my-client
stream:
  name: sample
  path: /resources
""".strip(),
    )

    class FakeDbutilsSecret:
        def __init__(self, value: str) -> None:
            self._value = value

        def __str__(self) -> str:
            return "***"

        def value(self) -> str:
            return self._value

    secret = FakeDbutilsSecret("secret-from-wrapper")
    config = load_config(config_path, options={"oauth_client_secret": secret})
    assert config.auth.client_secret == "secret-from-wrapper"


def test_partition_param_range_range_block(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        """
version: 0.1
source:
  type: rest
  base_url: https://api.test
stream:
  path: /objects
  partition:
    strategy: param_range
    param: page
    range_start: 1
    range_end: 5
    range_step: 2
    range_kind: numeric
""".strip(),
    )

    config = load_config(config_path)
    partition = config.stream.partition

    assert partition.strategy == "param_range"
    assert partition.param == "page"
    assert partition.range_start == 1
    assert partition.range_end == 5
    assert partition.range_step == 2
    assert partition.range_kind == "numeric"
    assert partition.values is None


def test_partition_param_range_values_list(tmp_path: Path) -> None:
    config_path = write_config(
        tmp_path,
        """
version: 0.1
source:
  type: rest
  base_url: https://api.test
stream:
  path: /objects
  partition:
    strategy: param_range
    param: status
    values:
      - new
      - closed
""".strip(),
    )

    config = load_config(config_path)
    partition = config.stream.partition

    assert partition.strategy == "param_range"
    assert partition.param == "status"
    assert partition.values == ("new", "closed")
    assert partition.range_start is None
    assert partition.range_end is None
    assert partition.range_step is None
    assert partition.range_kind is None
