import pytest

from polymo.config import (
    ConfigError,
    RestSourceConfig,
    config_to_dict,
    parse_config,
)


def test_parse_config_success() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.test",
        },
        "stream": {
            "name": "sample",
            "path": "/objects",
            "infer_schema": True,
        },
    }

    config = parse_config(raw)

    assert isinstance(config, RestSourceConfig)
    assert config.base_url == "https://api.test"
    assert config.auth.type == "none"
    assert config.stream.name == "sample"
    assert config.stream.infer_schema is True
    assert config.stream.error_handler.max_retries == 5
    assert config.stream.error_handler.retry_statuses == ("5XX", "429")


def test_parse_config_root_must_be_mapping() -> None:
    with pytest.raises(ConfigError):
        parse_config(["not", "a", "mapping"])


def test_invalid_auth_requires_token() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.test",
            "auth": {"type": "bearer"},
        },
        "streams": [{"name": "bad", "path": "/objects"}],
    }

    with pytest.raises(ConfigError):
        parse_config(raw)


def test_config_to_dict() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.test",
        },
        "stream": {
            "name": "sample",
            "path": "/objects",
            "params": {"limit": 10},
        },
    }

    config = parse_config(raw)
    config_dict = config_to_dict(config)
    assert config_dict["source"]["base_url"] == "https://api.test"
    assert config_dict["stream"]["params"]["limit"] == 10
    assert config_dict["stream"]["record_selector"] == {
        "field_path": [],
        "record_filter": None,
        "cast_to_schema_types": False,
    }
    assert config_dict["stream"]["error_handler"]["max_retries"] == 5


def test_record_selector_round_trip() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.test",
        },
        "stream": {
            "name": "sample",
            "path": "/objects",
            "record_selector": {
                "field_path": ["response", "docs"],
                "record_filter": "{{ record.status == 'active' }}",
                "cast_to_schema_types": True,
            },
            "schema": "id INT, status STRING",
        },
    }

    config = parse_config(raw)
    selector = config.stream.record_selector
    assert selector.field_path == ["response", "docs"]
    assert selector.record_filter == "{{ record.status == 'active' }}"
    assert selector.cast_to_schema_types is True


def test_custom_error_handler_round_trip() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.test",
        },
        "stream": {
            "name": "sample",
            "path": "/objects",
            "error_handler": {
                "max_retries": 2,
                "retry_statuses": [404, "5XX"],
                "retry_on_timeout": False,
                "backoff": {
                    "initial_delay_seconds": 0.5,
                    "max_delay_seconds": 4,
                    "multiplier": 1.5,
                },
            },
        },
    }

    config = parse_config(raw)
    handler = config.stream.error_handler
    assert handler.max_retries == 2
    assert handler.retry_statuses == ("404", "5XX")
    assert handler.retry_on_timeout is False
    assert handler.retry_on_connection_errors is True
    assert handler.backoff.initial_delay_seconds == 0.5
    assert handler.backoff.max_delay_seconds == 4.0
    assert handler.backoff.multiplier == 1.5

    config_dict = config_to_dict(config)
    assert "error_handler" in config_dict["stream"]


def test_oauth2_auth_uses_runtime_secret() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.oauth",
            "auth": {
                "type": "oauth2",
                "token_url": "https://auth.example.com/token",
                "client_id": "my-client",
                "scope": ["read", "write"],
            },
        },
        "stream": {
            "name": "sample",
            "path": "/resources",
        },
    }

    config = parse_config(raw, options={"oauth_client_secret": "s3cret"})
    assert config.auth.type == "oauth2"
    assert config.auth.token_url == "https://auth.example.com/token"
    assert config.auth.client_id == "my-client"
    assert config.auth.client_secret == "s3cret"
    assert config.auth.scope == ("read", "write")

    config_dict = config_to_dict(config)
    assert config_dict["source"]["auth"]["type"] == "oauth2"


def test_oauth2_auth_accepts_secret_wrappers() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.oauth",
            "auth": {
                "type": "oauth2",
                "token_url": "https://auth.example.com/token",
                "client_id": "my-client",
            },
        },
        "stream": {
            "name": "sample",
            "path": "/resources",
        },
    }

    class FakeDbutilsSecret:
        def __init__(self, value: str) -> None:
            self._value = value

        def __str__(self) -> str:
            return "***"

        def value(self) -> str:
            return self._value

    secret = FakeDbutilsSecret("secret-from-wrapper")
    config = parse_config(raw, options={"oauth_client_secret": secret})
    assert config.auth.client_secret == "secret-from-wrapper"


def test_partition_param_range_range_block() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.test",
        },
        "stream": {
            "path": "/objects",
            "partition": {
                "strategy": "param_range",
                "param": "page",
                "range_start": 1,
                "range_end": 5,
                "range_step": 2,
                "range_kind": "numeric",
            },
        },
    }

    config = parse_config(raw)
    partition = config.stream.partition

    assert partition.strategy == "param_range"
    assert partition.param == "page"
    assert partition.range_start == 1
    assert partition.range_end == 5
    assert partition.range_step == 2
    assert partition.range_kind == "numeric"
    assert partition.values is None


def test_partition_param_range_values_list() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.test",
        },
        "stream": {
            "path": "/objects",
            "partition": {
                "strategy": "param_range",
                "param": "status",
                "values": ["new", "closed"],
            },
        },
    }

    config = parse_config(raw)
    partition = config.stream.partition

    assert partition.strategy == "param_range"
    assert partition.param == "status"
    assert partition.values == ("new", "closed")
    assert partition.range_start is None
    assert partition.range_end is None
    assert partition.range_step is None
    assert partition.range_kind is None


def test_streaming_flag_defaults_false() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.test",
        },
        "stream": {
            "path": "/objects",
        },
    }

    config = parse_config(raw)

    assert config.stream.streaming is False
    assert config_to_dict(config)["stream"]["streaming"] is False


def test_streaming_flag_round_trip() -> None:
    raw = {
        "version": 0.1,
        "source": {
            "type": "rest",
            "base_url": "https://api.test",
        },
        "stream": {
            "path": "/objects",
            "schema": "id BIGINT",
            "streaming": True,
            "pagination": {
                "type": "page",
                "page_param": "page",
                "page_size": 10,
            },
        },
    }

    config = parse_config(raw)

    assert config.stream.streaming is True

    config_dict = config_to_dict(config)
    assert config_dict["stream"]["streaming"] is True

    # Round-trip through parse_config (as /api/generate does with config_dict payloads).
    reparsed = parse_config(config_dict)
    assert reparsed.stream.streaming is True


def test_response_format_defaults_to_json() -> None:
    raw = {
        "version": 0.1,
        "source": {"type": "rest", "base_url": "https://api.test"},
        "stream": {"path": "/objects"},
    }

    config = parse_config(raw)

    assert config.stream.response_format == "json"
    assert config.stream.xml_record_path is None
    assert config_to_dict(config)["stream"]["response_format"] == "json"
    assert config_to_dict(config)["stream"]["xml_record_path"] is None


def test_response_format_xml_round_trip() -> None:
    raw = {
        "version": 0.1,
        "source": {"type": "rest", "base_url": "https://api.test"},
        "stream": {
            "path": "/contacts",
            "response_format": "xml",
            "xml_record_path": ".//contact",
        },
    }

    config = parse_config(raw)

    assert config.stream.response_format == "xml"
    assert config.stream.xml_record_path == ".//contact"

    config_dict = config_to_dict(config)
    assert config_dict["stream"]["response_format"] == "xml"
    assert config_dict["stream"]["xml_record_path"] == ".//contact"

    reparsed = parse_config(config_dict)
    assert reparsed.stream.response_format == "xml"
    assert reparsed.stream.xml_record_path == ".//contact"


def test_response_format_rejects_unsupported_value() -> None:
    raw = {
        "version": 0.1,
        "source": {"type": "rest", "base_url": "https://api.test"},
        "stream": {"path": "/objects", "response_format": "yaml"},
    }

    with pytest.raises(ConfigError):
        parse_config(raw)


def test_xml_record_path_without_xml_format_is_config_error() -> None:
    raw = {
        "version": 0.1,
        "source": {"type": "rest", "base_url": "https://api.test"},
        "stream": {"path": "/objects", "xml_record_path": ".//contact"},
    }

    with pytest.raises(ConfigError):
        parse_config(raw)


def test_xml_format_without_record_path_is_config_error() -> None:
    raw = {
        "version": 0.1,
        "source": {"type": "rest", "base_url": "https://api.test"},
        "stream": {"path": "/objects", "response_format": "xml"},
    }

    with pytest.raises(ConfigError):
        parse_config(raw)
