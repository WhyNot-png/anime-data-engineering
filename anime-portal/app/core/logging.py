"""Единая настройка логирования для API и ETL-скриптов."""

import logging
import sys

from app.core.config import get_settings

_FORMAT = "%(asctime)s %(levelname)-8s %(name)s %(message)s"


def setup_logging(level: str | None = None) -> None:
    settings = get_settings()
    logging.basicConfig(
        level=(level or settings.log_level).upper(),
        format=_FORMAT,
        stream=sys.stdout,
        force=True,
    )
