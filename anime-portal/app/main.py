"""Точка входа FastAPI: API v1, Swagger, статический клиент и health-check."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app import __version__
from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import setup_logging
from app.db import SessionLocal

STATIC_DIR = Path(__file__).parent / "static"
logger = logging.getLogger("anime_portal")

DESCRIPTION = """
Информационная система каталога аниме: тайтлы, студии, жанры, списки просмотра,
отзывы с оценками и аналитика.

**Бизнес-правила**
1. Один тайтл — одна запись в списке просмотра пользователя (409 при повторе).
2. Прогресс не превышает число эпизодов; при достижении конца статус становится `completed`.
3. Отзыв доступен только после `completed`, один отзыв на тайтл.
4. Тайтл с отзывами удалить нельзя — оценки не теряются.
"""


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    setup_logging()
    logger.info("Anime Portal %s starting", __version__)
    yield
    logger.info("Anime Portal stopping")


app = FastAPI(
    title="Anime Portal API",
    version=__version__,
    description=DESCRIPTION,
    openapi_tags=[
        {"name": "anime", "description": "Каталог тайтлов: CRUD, фильтры, сортировка"},
        {"name": "studios", "description": "Студии-производители"},
        {"name": "genres", "description": "Жанры (связь многие-ко-многим)"},
        {"name": "users", "description": "Пользователи, списки просмотра и отзывы"},
        {"name": "analytics", "description": "Агрегированные отчёты"},
        {"name": "service", "description": "Служебные эндпоинты"},
    ],
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health", tags=["service"], summary="Проверка доступности приложения и БД")
def health(response: Response) -> dict[str, str]:
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
    except Exception:  # pragma: no cover - зависит от внешней БД
        logger.exception("Health check failed")
        response.status_code = 503
        return {"status": "degraded", "database": "unavailable", "version": __version__}
    return {"status": "ok", "database": "ok", "version": __version__}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    response = await call_next(request)
    logger.info("%s %s -> %s", request.method, request.url.path, response.status_code)
    return response


__all__ = ["app", "get_settings"]
