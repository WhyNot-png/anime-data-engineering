import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_engine, get_session, get_session_factory
from app.main import app
from app.models import Task, User


@pytest.fixture(scope="session", autouse=True)
def use_test_database():
    url = os.environ.get("TEST_DATABASE_URL")
    if not url or not (make_url(url).database or "").endswith("_test"):
        pytest.fail("Set TEST_DATABASE_URL to a migrated PostgreSQL database ending in _test")
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_session_factory.cache_clear()
    yield
    if previous is None:
        os.environ.pop("DATABASE_URL", None)
    else:
        os.environ["DATABASE_URL"] = previous
    get_settings.cache_clear()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def engine_cleanup(use_test_database):
    yield
    await get_engine().dispose()
    get_engine.cache_clear()
    get_session_factory.cache_clear()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    # Router commit releases a savepoint, not this outer transaction.
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        async with AsyncSession(
            bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        ) as session:
            assert await session.scalar(select(func.count()).select_from(User)) == 0, (
                "Dirty tasks_test users"
            )
            assert await session.scalar(select(func.count()).select_from(Task)) == 0, (
                "Dirty tasks_test tasks"
            )

            async def override_session():
                yield session

            app.dependency_overrides[get_session] = override_session
            try:
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as c:
                    yield c
            finally:
                app.dependency_overrides.clear()
                await transaction.rollback()
