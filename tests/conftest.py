"""Tests must not depend on a developer's environment or .env."""

import logging
import os
from collections.abc import Iterator
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    for key in list(os.environ):
        if key.startswith("RG_") or key in {
            "RAW_DATA_DIR",
            "PROCESSED_DATA_DIR",
            "DATABASE_URL",
            "KAGGLE_DATASET",
        }:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    root_logger = logging.getLogger()
    previous_handlers = root_logger.handlers[:]
    previous_level = root_logger.level
    # Detach pytest handlers so setup_logging cannot close them.
    root_logger.handlers = []
    previous_levels = {
        name: logging.getLogger(name).level
        for name in ("httpx", "httpcore", "urllib3", "asyncio", "kaggle", "sqlalchemy.engine")
    }
    yield
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        handler.close()
    root_logger.handlers = previous_handlers
    root_logger.setLevel(previous_level)
    for name, level in previous_levels.items():
        logging.getLogger(name).setLevel(level)
