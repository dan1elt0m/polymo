from pathlib import Path

import pytest

from polymo.config import (
    ConfigError,
    RestSourceConfig,
    config_to_dict,
    dump_config,
    load_config,
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

    yaml_text = dump_config(config)
    assert "base_url: https://api.test" in yaml_text
    assert "limit: 10" in yaml_text
