"""Проверка, что миграции обратимы и совпадают с моделями (защита от дрейфа схемы)."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

from app.db import Base


def _config(database_url: str, project_root: Path) -> Config:
    config = Config(str(project_root / "alembic.ini"))
    config.set_main_option("script_location", str(project_root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config


@pytest.fixture
def sqlite_url(tmp_path: Path) -> str:
    return f"sqlite:///{tmp_path / 'migration.db'}"


def test_upgrade_creates_all_tables(
    sqlite_url: str, project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    from app.core import config as config_module

    config_module.get_settings.cache_clear()
    try:
        command.upgrade(_config(sqlite_url, project_root), "head")
        engine = create_engine(sqlite_url)
        tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
        assert tables == set(Base.metadata.tables)
        engine.dispose()
    finally:
        config_module.get_settings.cache_clear()


def test_downgrade_removes_schema(
    sqlite_url: str, project_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("DATABASE_URL", sqlite_url)
    from app.core import config as config_module

    config_module.get_settings.cache_clear()
    try:
        config = _config(sqlite_url, project_root)
        command.upgrade(config, "head")
        command.downgrade(config, "base")
        engine = create_engine(sqlite_url)
        tables = set(inspect(engine).get_table_names()) - {"alembic_version"}
        assert tables == set()
        engine.dispose()
    finally:
        config_module.get_settings.cache_clear()
