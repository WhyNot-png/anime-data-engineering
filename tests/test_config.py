from pathlib import Path

import pytest
from pydantic import ValidationError

from research_graph.config import Settings, get_settings


def test_defaults() -> None:
    settings = get_settings()
    assert settings.github_token is None
    assert settings.data_dir == Path("data")
    assert settings.log_level == "INFO"
    assert settings.log_format == "text"
    assert settings.request_timeout == 30.0
    assert settings.max_concurrency == 8


def test_settings_read_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RG_LOG_LEVEL", "debug")
    monkeypatch.setenv("RG_MAX_CONCURRENCY", "16")
    monkeypatch.setenv("RG_REQUEST_TIMEOUT", "12.5")
    monkeypatch.setenv("RG_DATA_DIR", "custom/data")
    monkeypatch.setenv("RG_LOG_FORMAT", "json")
    settings = get_settings()
    assert settings.log_level == "DEBUG"
    assert settings.max_concurrency == 16
    assert settings.request_timeout == 12.5
    assert settings.data_dir == Path("custom/data")
    assert settings.log_format == "json"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("RG_MAX_CONCURRENCY", "0"),
        ("RG_MAX_CONCURRENCY", "65"),
        ("RG_MAX_CONCURRENCY", "bad"),
        ("RG_REQUEST_TIMEOUT", "0"),
        ("RG_REQUEST_TIMEOUT", "-1"),
        ("RG_REQUEST_TIMEOUT", "301"),
        ("RG_REQUEST_TIMEOUT", "nan"),
        ("RG_REQUEST_TIMEOUT", "inf"),
        ("RG_LOG_LEVEL", "TRACE"),
        ("RG_LOG_FORMAT", "xml"),
    ],
)
def test_reject_invalid_settings(monkeypatch: pytest.MonkeyPatch, key: str, value: str) -> None:
    monkeypatch.setenv(key, value)
    with pytest.raises(ValidationError):
        Settings()


def test_dotenv_and_env_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    Path(".env").write_text("RG_MAX_CONCURRENCY=3\nRG_LOG_LEVEL=DEBUG\nUNRELATED=value\n")
    assert get_settings().max_concurrency == 3
    monkeypatch.setenv("RG_MAX_CONCURRENCY", "4")
    assert get_settings().max_concurrency == 4
    assert get_settings().log_level == "DEBUG"


def test_ensure_directory_is_idempotent() -> None:
    settings = Settings(data_dir=Path("nested/data"))
    assert settings.ensure_data_dir() == Path("nested/data")
    assert settings.ensure_data_dir().is_dir()


def test_get_settings_does_not_cache_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    assert get_settings().log_level == "INFO"
    monkeypatch.setenv("RG_LOG_LEVEL", "ERROR")
    assert get_settings().log_level == "ERROR"


def test_token_is_not_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RG_GITHUB_TOKEN", "test-value-not-a-real-token")
    assert "test-value-not-a-real-token" not in repr(Settings())
