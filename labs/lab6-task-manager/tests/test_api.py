import logging

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.schemas import TaskUpdate, UserUpdate


async def user(client, email="alice@example.com"):
    response = await client.post("/users", json={"email": email, "name": "Alice"})
    assert response.status_code == 201
    return response.json()


async def task(client, owner_id, **updates):
    response = await client.post(
        "/tasks", json={"title": "Read paper", "owner_id": owner_id, **updates}
    )
    assert response.status_code == 201
    return response.json()


async def test_users_create_get_duplicate(client):
    created = await user(client)
    assert created["email"] == "alice@example.com" and created["created_at"]
    response = await client.get(f"/users/{created['id']}")
    assert response.status_code == 200 and response.json() == created
    duplicate = await client.post("/users", json={"email": created["email"], "name": "Other"})
    assert duplicate.status_code == 409
    # The session is usable after IntegrityError + rollback.
    assert (await client.get(f"/users/{created['id']}")).status_code == 200


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "invalid", "name": "A"},
        {"email": "a@example.com", "name": ""},
        {"email": "a@example.com"},
        {"email": "a@example.com", "name": "A", "id": 1},
    ],
)
async def test_users_validation(client, payload):
    assert (await client.post("/users", json=payload)).status_code == 422


async def test_missing_users_tasks_owner(client):
    assert (await client.get("/users/999999")).status_code == 404
    assert (await client.get("/tasks/999999")).status_code == 404
    assert (await client.patch("/tasks/999999", json={"done": True})).status_code == 404
    assert (await client.delete("/tasks/999999")).status_code == 404
    assert (await client.post("/tasks", json={"title": "A", "owner_id": 999999})).status_code == 404


async def test_task_crud_partial_null_and_delete(client):
    owner = await user(client)
    created = await task(client, owner["id"], description="Original")
    assert created["done"] is False and created["created_at"]
    url = f"/tasks/{created['id']}"
    assert (await client.get(url)).json() == created
    patched = await client.patch(url, json={"done": True})
    assert patched.status_code == 200
    assert patched.json()["title"] == "Read paper" and patched.json()["description"] == "Original"
    assert patched.json()["done"] is True
    cleared = await client.patch(url, json={"description": None})
    assert cleared.status_code == 200 and cleared.json()["description"] is None
    assert (await client.patch(url, json={})).status_code == 200
    deleted = await client.delete(url)
    assert deleted.status_code == 204 and deleted.content == b""
    assert (await client.get(url)).status_code == 404


async def test_patch_owner_and_title(client):
    first = await user(client)
    second = await user(client, "bob@example.com")
    created = await task(client, first["id"])
    url = f"/tasks/{created['id']}"
    response = await client.patch(url, json={"owner_id": second["id"], "title": "New title"})
    assert response.status_code == 200 and response.json()["owner_id"] == second["id"]
    assert response.json()["title"] == "New title"
    assert (await client.patch(url, json={"owner_id": 999999})).status_code == 404
    assert (await client.get(url)).json()["owner_id"] == second["id"]


@pytest.mark.parametrize(
    "patch",
    [
        {"title": ""},
        {"title": "x" * 201},
        {"title": None},
        {"done": None},
        {"owner_id": None},
        {"owner_id": 0},
        {"unknown": 5},
    ],
)
async def test_patch_validation(client, patch):
    owner = await user(client)
    created = await task(client, owner["id"])
    assert (await client.patch(f"/tasks/{created['id']}", json=patch)).status_code == 422


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "", "owner_id": 1},
        {"title": "x" * 201, "owner_id": 1},
        {"owner_id": 1},
        {"title": "A", "owner_id": 0},
        {"title": "A", "owner_id": 1, "done": None},
    ],
)
async def test_task_create_validation(client, payload):
    assert (await client.post("/tasks", json=payload)).status_code == 422


async def test_title_maximum_length(client):
    owner = await user(client)
    created = await task(client, owner["id"], title="x" * 200)
    assert len(created["title"]) == 200


async def test_filters_and_pagination(client):
    first = await user(client)
    second = await user(client, "bob@example.com")
    a = await task(client, first["id"], title="A", done=False)
    b = await task(client, first["id"], title="B", done=True)
    c = await task(client, second["id"], title="C", done=False)
    assert [x["id"] for x in (await client.get("/tasks")).json()] == [a["id"], b["id"], c["id"]]
    assert [x["id"] for x in (await client.get("/tasks?done=false")).json()] == [a["id"], c["id"]]
    assert [
        x["id"] for x in (await client.get(f"/tasks?done=true&owner_id={first['id']}")).json()
    ] == [b["id"]]
    assert [x["id"] for x in (await client.get("/tasks?limit=1&offset=1")).json()] == [b["id"]]
    assert (await client.get("/tasks?offset=10000")).json() == []


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "owner_id=0", "done=maybe"])
async def test_query_validation(client, query):
    assert (await client.get("/tasks?" + query)).status_code == 422


async def test_middleware_and_docs(client, caplog):
    with caplog.at_level(logging.INFO, logger="task_manager.http"):
        for path, expected in [("/tasks", 200), ("/users/999999", 404), ("/tasks?limit=0", 422)]:
            response = await client.get(path)
            assert response.status_code == expected
            assert float(response.headers["X-Process-Time"]) >= 0
    assert "GET /users/999999 status=404 duration=" in caplog.text
    assert (await client.get("/docs")).status_code == 200
    spec = (await client.get("/openapi.json")).json()
    assert set(spec["paths"]) == {"/users", "/users/{id}", "/tasks", "/tasks/{id}"}


def test_update_unset_vs_null():
    assert TaskUpdate().model_dump(exclude_unset=True) == {}
    assert TaskUpdate(description=None).model_dump(exclude_unset=True) == {"description": None}
    assert UserUpdate().model_dump(exclude_unset=True) == {}
    assert UserUpdate(name="Alice").name == "Alice"
    for field in ["name", "email"]:
        with pytest.raises(ValidationError):
            UserUpdate(**{field: None})


def test_config_rejects_non_postgresql():
    with pytest.raises(ValidationError):
        Settings(database_url="sqlite:///example.db", _env_file=None)


async def test_real_session_dependency():
    from contextlib import aclosing

    from sqlalchemy import text

    from app.db import get_session

    async with aclosing(get_session()) as sessions:
        session = await anext(sessions)
        assert await session.scalar(text("SELECT 1")) == 1


async def test_lifespan_disposes_engine():
    from app.main import app, lifespan

    async with lifespan(app):
        assert app.title.startswith("Task Manager")
