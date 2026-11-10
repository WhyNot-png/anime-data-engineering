"""Интеграционные тесты API каталога через TestClient."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.review import Review


def test_list_default_page(client: TestClient, anime) -> None:
    response = client.get("/api/v1/anime")
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["page"] == 1 and body["pages"] == 1
    assert body["items"][0]["title"] == "Death Note"
    assert body["items"][0]["studio"]["name"] == "Madhouse"
    assert body["items"][0]["reviews_count"] == 0


def test_list_filters_and_sorting(client: TestClient, anime, studio, genres) -> None:
    client.post("/api/v1/anime", json={"title": "Older", "year": 1998, "studio_id": studio.id})
    by_year = client.get("/api/v1/anime", params={"sort": "-year", "size": 10}).json()
    assert [item["year"] for item in by_year["items"]] == [2006, 1998]

    searched = client.get("/api/v1/anime", params={"q": "old"}).json()
    assert searched["total"] == 1

    by_genre = client.get("/api/v1/anime", params={"genre": "action"}).json()
    assert by_genre["total"] == 1

    by_status = client.get("/api/v1/anime", params={"status": "upcoming"}).json()
    assert by_status["total"] == 0

    ranged = client.get("/api/v1/anime", params={"year_from": 2000, "year_to": 2010}).json()
    assert ranged["total"] == 1


def test_list_pagination_and_limits(client: TestClient, anime) -> None:
    for index in range(3):
        client.post("/api/v1/anime", json={"title": f"Extra {index}"})
    page = client.get("/api/v1/anime", params={"page": 2, "size": 2}).json()
    assert page["total"] == 4 and page["pages"] == 2 and len(page["items"]) == 2
    assert client.get("/api/v1/anime", params={"page": 0}).status_code == 422
    assert client.get("/api/v1/anime", params={"size": 1000}).status_code == 422


def test_list_invalid_sort_returns_unified_error(client: TestClient) -> None:
    response = client.get("/api/v1/anime", params={"sort": "title; DROP TABLE anime"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_create_update_delete_flow(client: TestClient, studio, genres) -> None:
    created = client.post(
        "/api/v1/anime",
        json={
            "title": "Steins;Gate",
            "year": 2011,
            "episodes": 24,
            "studio_id": studio.id,
            "genre_ids": [genres[0].id],
        },
    )
    assert created.status_code == 201
    anime_id = created.json()["id"]
    assert created.json()["genres"][0]["name"] == "Action"

    patched = client.patch(f"/api/v1/anime/{anime_id}", json={"episodes": 25})
    assert patched.status_code == 200 and patched.json()["episodes"] == 25

    assert client.delete(f"/api/v1/anime/{anime_id}").status_code == 204
    assert client.get(f"/api/v1/anime/{anime_id}").status_code == 404


def test_create_validation_errors(client: TestClient) -> None:
    empty = client.post("/api/v1/anime", json={"title": "   "})
    assert empty.status_code == 422
    details = empty.json()["error"]["details"]
    assert details[0]["field"] == "title"

    bad_year = client.post("/api/v1/anime", json={"title": "Old", "year": 1500})
    assert bad_year.status_code == 422

    bad_genre = client.post("/api/v1/anime", json={"title": "New", "genre_ids": [42]})
    assert bad_genre.status_code == 422
    assert "42" in bad_genre.json()["error"]["message"]


def test_duplicate_title_conflict(client: TestClient, anime) -> None:
    response = client.post("/api/v1/anime", json={"title": "Death Note"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"


def test_not_found_paths(client: TestClient) -> None:
    assert client.get("/api/v1/anime/9999").status_code == 404
    assert client.patch("/api/v1/anime/9999", json={"year": 2000}).status_code == 404
    assert client.delete("/api/v1/anime/9999").status_code == 404
    unknown_route = client.get("/api/v1/unknown")
    assert unknown_route.status_code == 404
    assert unknown_route.json()["error"]["code"] == "not_found"


def test_delete_blocked_by_reviews(client: TestClient, session: Session, anime, user) -> None:
    session.add(Review(user_id=user.id, anime_id=anime.id, rating=10))
    session.commit()
    response = client.delete(f"/api/v1/anime/{anime.id}")
    assert response.status_code == 409
    assert "отзыв" in response.json()["error"]["message"]


def test_dictionaries(client: TestClient, anime, studio, genres) -> None:
    studios = client.get("/api/v1/studios").json()
    assert studios["total"] == 1
    assert client.get("/api/v1/genres").json()[0]["slug"] == "action"

    created = client.post("/api/v1/genres", json={"name": "Mecha"})
    assert created.status_code == 201 and created.json()["slug"] == "mecha"
    assert client.post("/api/v1/genres", json={"name": "Mecha"}).status_code == 409

    blocked = client.delete(f"/api/v1/studios/{studio.id}")
    assert blocked.status_code == 409
    empty_studio = client.post("/api/v1/studios", json={"name": "Empty"}).json()
    assert client.delete(f"/api/v1/studios/{empty_studio['id']}").status_code == 204
    assert client.delete("/api/v1/studios/999").status_code == 404


def test_openapi_documents_endpoints(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    assert "/api/v1/anime" in schema["paths"]
    assert "/api/v1/analytics/top-anime" in schema["paths"]
    assert schema["info"]["title"] == "Anime Portal API"


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code in {200, 503}
    assert response.json()["status"] in {"ok", "degraded"}
