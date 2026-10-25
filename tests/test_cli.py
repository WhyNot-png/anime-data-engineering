import json

import pytest
from typer.testing import CliRunner

from research_graph import __version__
from research_graph.cli import app

runner = CliRunner()


def test_version_command() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert result.stdout.strip() == __version__


def test_help_lists_commands() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.stdout
    assert "check-config" in result.stdout


@pytest.mark.parametrize("log_format", ["text", "json"])
def test_check_config_hides_token(monkeypatch: pytest.MonkeyPatch, log_format: str) -> None:
    secret = "ghp_supersecretvalue"
    monkeypatch.setenv("RG_GITHUB_TOKEN", secret)
    monkeypatch.setenv("RG_LOG_FORMAT", log_format)
    result = runner.invoke(app, ["check-config"])
    assert result.exit_code == 0
    assert secret not in result.output
    assert secret not in result.stderr
    summary = json.loads(result.stdout)
    assert summary["github_token_configured"] is True
    assert summary["log_format"] == log_format
    assert summary["max_concurrency"] == 8
    assert "Configuration validated" in result.stderr
    if log_format == "json":
        assert json.loads(result.stderr)["level"] == "INFO"


def test_no_token_and_no_directory_side_effect() -> None:
    result = runner.invoke(app, ["check-config"])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["github_token_configured"] is False


def test_invalid_config_does_not_echo_raw_input(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "a-sensitive-value-accidentally-pasted-as-timeout"
    monkeypatch.setenv("RG_REQUEST_TIMEOUT", secret)
    result = runner.invoke(app, ["check-config"])
    assert result.exit_code == 2
    assert secret not in result.output + result.stderr
    assert "Invalid configuration" in result.stderr
