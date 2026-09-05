import sys

import pytest

from polymo.cli import _require_ui_deps, main


def test_help_works():
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0


def test_bare_command_launches_ui_with_defaults(monkeypatch):
    calls = {}

    def fake_run(app, **kwargs):
        calls["app"] = app
        calls["kwargs"] = kwargs

    monkeypatch.setattr("uvicorn.run", fake_run)

    assert main([]) == 0
    assert calls["app"] == "polymo.ui.app:create_app"
    assert calls["kwargs"]["host"] == "127.0.0.1"
    assert calls["kwargs"]["port"] == 8000
    assert calls["kwargs"]["reload"] is False
    assert calls["kwargs"]["factory"] is True


def test_port_flag_is_honored(monkeypatch):
    calls = {}

    def fake_run(app, **kwargs):
        calls["kwargs"] = kwargs

    monkeypatch.setattr("uvicorn.run", fake_run)

    assert main(["--port", "9000"]) == 0
    assert calls["kwargs"]["port"] == 9000


def test_subcommands_are_rejected():
    """No subparsers exist; the pre-1.2 `polymo builder` is an unrecognized arg."""
    with pytest.raises(SystemExit) as excinfo:
        main(["builder"])
    assert excinfo.value.code == 2


def test_require_ui_deps_returns_true_when_pyspark_importable():
    assert _require_ui_deps() is True


def test_require_ui_deps_friendly_message_when_pyspark_missing(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "pyspark", None)
    assert _require_ui_deps() is False
    out = capsys.readouterr().out
    assert "polymo's dependencies are incomplete" in out
    assert "pip install --force-reinstall polymo" in out


def test_main_returns_1_without_traceback_when_pyspark_missing(monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "pyspark", None)
    assert main([]) == 1
    out = capsys.readouterr().out
    assert "polymo's dependencies are incomplete" in out


def test_main_does_not_launch_ui_when_pyspark_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyspark", None)

    called = False

    def fake_run(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr("uvicorn.run", fake_run)

    assert main([]) == 1
    assert called is False
