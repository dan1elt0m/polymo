import pytest

from polymo.cli import main


def test_builder_help_works():
    with pytest.raises(SystemExit) as excinfo:
        main(["builder", "--help"])
    assert excinfo.value.code == 0


def test_no_command_shows_help(capsys):
    assert main([]) == 1
    assert "builder" in capsys.readouterr().out


def test_unknown_command_rejected():
    with pytest.raises(SystemExit) as excinfo:
        main(["smoke"])
    assert excinfo.value.code == 2
