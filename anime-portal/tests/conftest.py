"""Общие фикстуры: отдельная тестовая БД на файле и клиент FastAPI с откатом транзакций."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session

from app.db import Base, get_session
from app.main import app
from app.models.anime import Anime
from app.models.genre import Genre
from app.models.studio import Studio
from app.models.user import User


@pytest.fixture
def engine(tmp_path: Path) -> Iterator[Engine]:
    """Своя БД на каждый тест: полная изоляция без хрупких откатов транзакций."""
    test_engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(test_engine)
    try:
        yield test_engine
    finally:
        test_engine.dispose()


@pytest.fixture
def session(engine: Engine) -> Iterator[Session]:
    db_session = Session(bind=engine)
    try:
        yield db_session
    finally:
        db_session.close()


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def studio(session: Session) -> Studio:
    studio = Studio(name="Madhouse", country="Japan", founded_year=1972)
    session.add(studio)
    session.commit()
    return studio


@pytest.fixture
def genres(session: Session) -> list[Genre]:
    items = [Genre(name="Action", slug="action"), Genre(name="Drama", slug="drama")]
    session.add_all(items)
    session.commit()
    return items


@pytest.fixture
def anime(session: Session, studio: Studio, genres: list[Genre]) -> Anime:
    item = Anime(
        title="Death Note",
        year=2006,
        episodes=37,
        status="finished",
        studio=studio,
        genres=genres,
    )
    session.add(item)
    session.commit()
    return item


@pytest.fixture
def user(session: Session) -> User:
    user = User(email="fan@example.com", username="fan")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def second_user(session: Session) -> User:
    user = User(email="critic@example.com", username="critic")
    session.add(user)
    session.commit()
    return user


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[1]
