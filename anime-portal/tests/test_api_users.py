"""Интеграционные тесты списков просмотра и отзывов, включая негативные сценарии."""

from fastapi.testclient import TestClient


def test_create_and_list_users(client: TestClient) -> None:
    created = client.post("/api/v1/users", json={"email": "Fan@Example.com", "username": "fan1"})
    assert created.status_code == 201
    assert created.json()["email"] == "fan@example.com"

    assert (
        client.post(
            "/api/v1/users", json={"email": "fan@example.com", "username": "other"}
        ).status_code
        == 409
    )
    assert (
        client.post(
            "/api/v1/users", json={"email": "fan2@example.com", "username": "fan1"}
        ).status_code
        == 409
    )
    assert (
        client.post("/api/v1/users", json={"email": "not-an-email", "username": "x"}).status_code
        == 422
    )

    listing = client.get("/api/v1/users").json()
    assert listing["total"] == 1
    assert client.get(f"/api/v1/users/{created.json()['id']}").status_code == 200
    assert client.get("/api/v1/users/999").status_code == 404


def test_watchlist_flow_with_autocompletion(client: TestClient, anime, user) -> None:
    added = client.post(
        f"/api/v1/users/{user.id}/watchlist", json={"anime_id": anime.id, "progress": 1}
    )
    assert added.status_code == 201
    entry = added.json()
    assert entry["status"] == "watching"
    assert entry["anime"]["title"] == "Death Note"

    assert (
        client.post(f"/api/v1/users/{user.id}/watchlist", json={"anime_id": anime.id}).status_code
        == 409
    )

    finished = client.patch(f"/api/v1/watchlist/{entry['id']}", json={"progress": 37})
    assert finished.status_code == 200
    assert finished.json()["status"] == "completed"

    listing = client.get(f"/api/v1/users/{user.id}/watchlist", params={"status": "completed"})
    assert listing.json()["total"] == 1

    assert client.delete(f"/api/v1/watchlist/{entry['id']}").status_code == 204
    assert client.get(f"/api/v1/users/{user.id}/watchlist").json()["total"] == 0


def test_watchlist_negative_cases(client: TestClient, anime, user) -> None:
    entry = client.post(f"/api/v1/users/{user.id}/watchlist", json={"anime_id": anime.id}).json()

    over = client.patch(f"/api/v1/watchlist/{entry['id']}", json={"progress": 999})
    assert over.status_code == 409
    assert "превышает" in over.json()["error"]["message"]

    early_complete = client.patch(
        f"/api/v1/watchlist/{entry['id']}", json={"status": "completed", "progress": 3}
    )
    assert early_complete.status_code == 409

    empty_patch = client.patch(f"/api/v1/watchlist/{entry['id']}", json={})
    assert empty_patch.status_code == 422

    assert (
        client.post("/api/v1/users/999/watchlist", json={"anime_id": anime.id}).status_code == 404
    )
    assert (
        client.post(f"/api/v1/users/{user.id}/watchlist", json={"anime_id": 999}).status_code == 404
    )
    assert client.patch("/api/v1/watchlist/999", json={"progress": 1}).status_code == 404
    assert client.delete("/api/v1/watchlist/999").status_code == 404


def test_reviews_require_completed_and_are_unique(client: TestClient, anime, user) -> None:
    before = client.post(f"/api/v1/anime/{anime.id}/reviews?user_id={user.id}", json={"rating": 9})
    assert before.status_code == 409
    assert "список просмотра" in before.json()["error"]["message"]

    client.post(
        f"/api/v1/users/{user.id}/watchlist",
        json={"anime_id": anime.id, "status": "completed", "progress": 37},
    )
    created = client.post(
        f"/api/v1/anime/{anime.id}/reviews?user_id={user.id}",
        json={"rating": 9, "body": "Отлично"},
    )
    assert created.status_code == 201

    duplicate = client.post(
        f"/api/v1/anime/{anime.id}/reviews?user_id={user.id}", json={"rating": 5}
    )
    assert duplicate.status_code == 409

    invalid_rating = client.post(
        f"/api/v1/anime/{anime.id}/reviews?user_id={user.id}", json={"rating": 11}
    )
    assert invalid_rating.status_code == 422

    listing = client.get(f"/api/v1/anime/{anime.id}/reviews").json()
    assert listing["total"] == 1
    assert client.get("/api/v1/anime/999/reviews").status_code == 404

    review_id = created.json()["id"]
    assert client.delete(f"/api/v1/reviews/{review_id}").status_code == 204
    assert client.delete(f"/api/v1/reviews/{review_id}").status_code == 404
