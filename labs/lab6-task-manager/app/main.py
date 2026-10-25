import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.db import get_engine
from app.routers import tasks, users

logger = logging.getLogger("task_manager.http")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    yield
    await get_engine().dispose()


app = FastAPI(title="Task Manager — Задание 6", version="0.1.0", lifespan=lifespan)
app.include_router(users.router)
app.include_router(tasks.router)


@app.middleware("http")
async def process_time(request: Request, call_next) -> Response:
    started = time.perf_counter()
    response = await call_next(request)
    elapsed = time.perf_counter() - started
    response.headers["X-Process-Time"] = f"{elapsed:.6f}"
    logger.info(
        "%s %s status=%d duration=%.6fs",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
    )
    return response
