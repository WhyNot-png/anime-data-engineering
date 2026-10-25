"""Real HTTP CRUD smoke test; use only the local teaching API."""

import json
import os
import time
import urllib.error
import urllib.request

base = os.environ.get("API_URL", "http://127.0.0.1:8000").rstrip("/")


def request(method, path, expected, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        base + path, data=data, method=method, headers={"Content-Type": "application/json"}
    )
    try:
        response = urllib.request.urlopen(req, timeout=15)
    except urllib.error.HTTPError as exc:
        response = exc
    payload = response.read()
    assert response.status == expected, (method, path, response.status, payload)
    assert float(response.headers["X-Process-Time"]) >= 0
    print(method, path, response.status)
    return json.loads(payload) if payload else None


email = f"smoke-{time.time_ns()}@example.com"
user = request("POST", "/users", 201, {"email": email, "name": "Smoke Student"})
request("POST", "/users", 409, {"email": email, "name": "Duplicate"})
request("GET", f"/users/{user['id']}", 200)
task = request("POST", "/tasks", 201, {"title": "Smoke test", "owner_id": user["id"]})
request("GET", f"/tasks/{task['id']}", 200)
rows = request("GET", f"/tasks?owner_id={user['id']}&done=false&limit=1&offset=0", 200)
assert rows[0]["id"] == task["id"]
updated = request("PATCH", f"/tasks/{task['id']}", 200, {"done": True})
assert updated["done"] is True
request("GET", "/tasks?limit=101", 422)
request("DELETE", f"/tasks/{task['id']}", 204)
request("GET", f"/tasks/{task['id']}", 404)
print("All HTTP smoke checks passed")
