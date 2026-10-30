import os

import pytest

from av_analyzer import cli


@pytest.fixture
def started(monkeypatch):
    calls = {}
    monkeypatch.delenv("AVA_HOST", raising=False)
    monkeypatch.delenv("AVA_PORT", raising=False)
    monkeypatch.setattr(cli.uvicorn, "run", lambda *args, **kwargs: calls.update(kwargs))
    return calls


def _dotenv_with_port(monkeypatch, port: str):
    def fake_load_dotenv(*_args, **_kwargs):
        # python-dotenv does not override variables already set; mirror that here.
        if "AVA_PORT" not in os.environ:
            monkeypatch.setenv("AVA_PORT", port)
        return True

    monkeypatch.setattr(cli, "load_dotenv", fake_load_dotenv, raising=False)


def test_port_from_dotenv_is_used(monkeypatch, started):
    _dotenv_with_port(monkeypatch, "9000")
    monkeypatch.setattr("sys.argv", ["av-analyzer"])
    cli.main()
    assert started["port"] == 9000


def test_environment_overrides_dotenv(monkeypatch, started):
    monkeypatch.setenv("AVA_PORT", "9100")
    _dotenv_with_port(monkeypatch, "9000")
    monkeypatch.setattr("sys.argv", ["av-analyzer"])
    cli.main()
    assert started["port"] == 9100


def test_command_line_overrides_dotenv(monkeypatch, started):
    _dotenv_with_port(monkeypatch, "9000")
    monkeypatch.setattr("sys.argv", ["av-analyzer", "--port", "9200"])
    cli.main()
    assert started["port"] == 9200
    assert started["host"] == "127.0.0.1"
