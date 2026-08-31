import sys

import pytest

from polymo.cli import _require_builder_deps, main


def test_builder_help_works():
    with pytest.raises(SystemExit) as excinfo:
        main(["builder", "--help"])
    assert excinfo.value.code == 0


def test_no_command_shows_help(capsys):
    assert main([]) == 1
    assert "builder" in capsys.readouterr().out


def test_no_command_shows_help_without_pyspark(monkeypatch, capsys):
    """main([]) must not require pyspark at all to print help."""
    monkeypatch.setitem(sys.modules, "pyspark", None)
    assert main([]) == 1
    assert "builder" in capsys.readouterr().out


def test_unknown_command_rejected():
    with pytest.raises(SystemExit) as excinfo:
        main(["smoke"])
    assert excinfo.value.code == 2


def test_require_builder_deps_returns_true_when_pyspark_importable():
    assert _require_builder_deps() is True


def test_require_builder_deps_friendly_message_when_pyspark_missing(
    monkeypatch, capsys
):
    monkeypatch.setitem(sys.modules, "pyspark", None)
    assert _require_builder_deps() is False
    assert "polymo[builder]" in capsys.readouterr().out


def test_builder_command_returns_1_without_traceback_when_pyspark_missing(
    monkeypatch, capsys
):
    monkeypatch.setitem(sys.modules, "pyspark", None)
    assert main(["builder"]) == 1
    assert "polymo[builder]" in capsys.readouterr().out
