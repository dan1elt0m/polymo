import pytest

from polymo.cli import main


def test_builder_help_works():
    with pytest.raises(SystemExit) as excinfo:
        main(["builder", "--help"])
    assert excinfo.value.code == 0
