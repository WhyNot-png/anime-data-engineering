"""Nine independent acceptance tests from assignment 7, step 4."""


async def make_user(client, email="required@example.com"):
    response = await client.post("/users", json={"email": email, "name": "Student"})
    assert response.status_code == 201
    return response.json()


async def make_task(client, owner_id, **fields):
    response = await client.post("/tasks", json={"title": "Task", "owner_id": owner_id, **fields})
    assert response.status_code == 201
    return response.json()


async def test_01_create_user_201(client):
    response = await client.post("/users", json={"email": "new@example.com", "name": "New"})
    assert response.status_code == 418  # Intentional failure: assignment 7 step 8.
    assert response.json()["email"] == "new@example.com"
    assert response.json()["id"] > 0


async def test_02_duplicate_email_409(client):
    user = await make_user(client)
    response = await client.post("/users", json={"email": user["email"], "name": "Duplicate"})
    assert response.status_code == 409
    assert response.json()["detail"] == "Email already registered"


async def test_03_invalid_email_422(client):
    response = await client.post("/users", json={"email": "not-an-email", "name": "Invalid"})
    assert response.status_code == 422
    assert any(item["loc"][-1] == "email" for item in response.json()["detail"])


async def test_04_create_task_201(client):
    user = await make_user(client)
    response = await client.post("/tasks", json={"title": "Prepare report", "owner_id": user["id"]})
    assert response.status_code == 201
    assert response.json()["owner_id"] == user["id"]
    assert response.json()["done"] is False


async def test_05_missing_owner_404(client):
    response = await client.post("/tasks", json={"title": "No owner", "owner_id": 99999999})
    assert response.status_code == 404
    assert response.json()["detail"] == "Owner not found"


async def test_06_done_filter_and_pagination(client):
    user = await make_user(client)
    a = await make_task(client, user["id"], title="A", done=False)
    await make_task(client, user["id"], title="B", done=True)
    c = await make_task(client, user["id"], title="C", done=False)
    response = await client.get("/tasks?done=false&limit=1&offset=1")
    assert response.status_code == 200
    assert [item["id"] for item in response.json()] == [c["id"]]
    assert response.json()[0]["id"] != a["id"]


async def test_07_patch_changes_only_provided_fields(client):
    user = await make_user(client)
    task = await make_task(client, user["id"], title="Keep title", description="Keep description")
    response = await client.patch(f"/tasks/{task['id']}", json={"done": True})
    assert response.status_code == 200
    assert response.json()["done"] is True
    for field in ["title", "description", "owner_id", "created_at"]:
        assert response.json()[field] == task[field]


async def test_08_delete_then_get_404(client):
    user = await make_user(client)
    task = await make_task(client, user["id"])
    response = await client.delete(f"/tasks/{task['id']}")
    assert response.status_code == 204 and response.content == b""
    assert (await client.get(f"/tasks/{task['id']}")).status_code == 404


async def test_09_process_time_header(client):
    response = await client.get("/tasks")
    assert response.status_code == 200
    assert "X-Process-Time" in response.headers
    assert float(response.headers["X-Process-Time"]) >= 0
