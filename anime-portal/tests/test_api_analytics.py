"""Интеграционные тесты аналитических эндпоинтов."""

from fastapi.testclient import TestClient


def _complete_and_review(
    client: TestClient, user_id: int, anime_id: int, episodes: int, rating: int
) -> None:
    client.post(
        f"/api/v1/users/{user_id}/watchlist",
        json={"anime_id": anime_id, "status": "completed", "progress": episodes},
    )
    assert (
        client.post(
            f"/api/v1/anime/{anime_id}/reviews?user_id={user_id}", json={"rating": rating}
        ).status_code
        == 201
    )


def test_top_anime_endpoint(client: TestClient, anime, user, second_user, genres) -> None:
    other = client.post(
        "/api/v1/anime", json={"title": "Weak Show", "episodes": 12, "genre_ids": [genres[0].id]}
    ).json()
    _complete_and_review(client, user.id, anime.id, 37, 10)
    _complete_and_review(client, second_user.id, anime.id, 37, 8)
    _complete_and_review(client, user.id, other["id"], 12, 5)

    top = client.get("/api/v1/analytics/top-anime", params={"limit": 2}).json()
    assert top[0]["title"] == "Death Note"
    assert top[0]["rating_avg"] == 9.0
    assert top[0]["reviews_count"] == 2

    strict = client.get("/api/v1/analytics/top-anime", params={"min_reviews": 2}).json()
    assert [item["title"] for item in strict] == ["Death Note"]

    assert client.get("/api/v1/analytics/top-anime", params={"limit": 0}).status_code == 422


def test_genre_and_year_stats(client: TestClient, anime, user, genres) -> None:
    _complete_and_review(client, user.id, anime.id, 37, 9)

    genres_stats = client.get("/api/v1/analytics/genres").json()
    action = next(item for item in genres_stats if item["genre"] == "Action")
    assert action["anime_count"] == 1
    assert action["avg_rating"] == 9.0

    years = client.get("/api/v1/analytics/years").json()
    assert years == [{"year": 2006, "titles": 1, "episodes_total": 37}]
    assert client.get("/api/v1/analytics/years", params={"year_from": 2010}).json() == []
    assert client.get("/api/v1/analytics/years", params={"year_from": 1800}).status_code == 422
