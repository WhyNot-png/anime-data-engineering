"""Unit-тесты сервисного слоя: бизнес-правила без HTTP."""

import pytest
from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, ValidationAppError
from app.models.anime import Anime
from app.models.review import Review
from app.models.user import User
from app.models.watch import WatchEntry
from app.schemas.anime import AnimeCreate, AnimeUpdate
from app.schemas.review import ReviewCreate
from app.schemas.watch import WatchEntryCreate, WatchEntryUpdate
from app.services import analytics, catalog, reviews, watchlist


def test_create_anime_links_studio_and_genres(session: Session, studio, genres) -> None:
    created = catalog.create_anime(
        session,
        AnimeCreate(
            title="Steins;Gate",
            year=2011,
            episodes=24,
            studio_id=studio.id,
            genre_ids=[genres[0].id],
        ),
    )
    assert created.id
    assert created.studio is not None and created.studio.name == "Madhouse"
    assert [genre.name for genre in created.genres] == ["Action"]
    assert created.rating_avg is None and created.reviews_count == 0


def test_create_anime_rejects_duplicate_title(session: Session, anime) -> None:
    with pytest.raises(ConflictError):
        catalog.create_anime(session, AnimeCreate(title="Death Note"))


def test_create_anime_validates_studio_and_genres(session: Session) -> None:
    with pytest.raises(ValidationAppError):
        catalog.create_anime(session, AnimeCreate(title="A", studio_id=999))
    with pytest.raises(ValidationAppError):
        catalog.create_anime(session, AnimeCreate(title="B", genre_ids=[999]))


def test_update_anime_partial_and_conflict(session: Session, anime) -> None:
    other = catalog.create_anime(session, AnimeCreate(title="Other"))
    updated = catalog.update_anime(session, anime.id, AnimeUpdate(year=2007))
    assert updated.year == 2007
    assert updated.title == "Death Note"
    with pytest.raises(ConflictError):
        catalog.update_anime(session, other.id, AnimeUpdate(title="Death Note"))


def test_update_anime_clears_optional_fields(session: Session, anime) -> None:
    updated = catalog.update_anime(session, anime.id, AnimeUpdate(year=None, synopsis=None))
    assert updated.year is None
    assert updated.synopsis is None


def test_delete_anime_blocked_by_reviews(session: Session, anime, user) -> None:
    session.add(Review(user_id=user.id, anime_id=anime.id, rating=9))
    session.commit()
    with pytest.raises(ConflictError, match="отзыв"):
        catalog.delete_anime(session, anime.id)


def test_delete_anime_without_reviews(session: Session, anime) -> None:
    catalog.delete_anime(session, anime.id)
    with pytest.raises(NotFoundError):
        catalog.get_anime(session, anime.id)


def test_list_anime_filters_sort_and_paginates(session: Session, studio, genres) -> None:
    for index in range(5):
        catalog.create_anime(
            session,
            AnimeCreate(
                title=f"Title {index}",
                year=2000 + index,
                episodes=10 + index,
                studio_id=studio.id,
                genre_ids=[genres[0].id],
            ),
        )
    filters = catalog.AnimeFilters(q="title", year_from=2002, year_to=2004, sort="-year", size=2)
    items, total = catalog.list_anime(session, filters)
    assert total == 3
    assert [item.year for item in items] == [2004, 2003]

    by_genre = catalog.list_anime(session, catalog.AnimeFilters(genre="action", size=10))
    assert by_genre[1] == 5

    page2 = catalog.list_anime(session, catalog.AnimeFilters(sort="title", page=2, size=2))
    assert [item.title for item in page2[0]] == ["Title 2", "Title 3"]


def test_list_anime_rejects_bad_sort(session: Session) -> None:
    with pytest.raises(ValidationAppError):
        catalog.list_anime(session, catalog.AnimeFilters(sort="drop table"))


def test_watchlist_autocompletes_on_last_episode(session: Session, anime, user) -> None:
    entry = watchlist.add_entry(session, user.id, WatchEntryCreate(anime_id=anime.id))
    assert entry.status == "planned"
    entry = watchlist.update_entry(session, entry.id, WatchEntryUpdate(progress=36))
    assert entry.status == "watching"
    entry = watchlist.update_entry(session, entry.id, WatchEntryUpdate(progress=37))
    assert entry.status == "completed"


def test_watchlist_prevents_duplicates(session: Session, anime, user) -> None:
    watchlist.add_entry(session, user.id, WatchEntryCreate(anime_id=anime.id))
    with pytest.raises(ConflictError, match="уже добавлен"):
        watchlist.add_entry(session, user.id, WatchEntryCreate(anime_id=anime.id))


def test_watchlist_rejects_progress_over_episodes(session: Session, anime, user) -> None:
    entry = watchlist.add_entry(session, user.id, WatchEntryCreate(anime_id=anime.id))
    with pytest.raises(ConflictError, match="превышает"):
        watchlist.update_entry(session, entry.id, WatchEntryUpdate(progress=100))


def test_watchlist_completed_requires_all_episodes(session: Session, anime, user) -> None:
    entry = watchlist.add_entry(session, user.id, WatchEntryCreate(anime_id=anime.id))
    with pytest.raises(ConflictError, match="Нельзя завершить"):
        watchlist.update_entry(session, entry.id, WatchEntryUpdate(status="completed", progress=5))


def test_watchlist_watching_requires_progress(session: Session, anime, user) -> None:
    with pytest.raises(ValidationAppError):
        watchlist.add_entry(
            session, user.id, WatchEntryCreate(anime_id=anime.id, status="watching")
        )


def test_watchlist_unknown_episode_count_is_unbounded(session: Session, user) -> None:
    item = catalog.create_anime(session, AnimeCreate(title="Unknown episodes"))
    entry = watchlist.add_entry(session, user.id, WatchEntryCreate(anime_id=item.id))
    entry = watchlist.update_entry(session, entry.id, WatchEntryUpdate(progress=500))
    assert entry.progress == 500
    assert entry.status == "watching"


def test_watchlist_requires_known_user_and_anime(session: Session, anime) -> None:
    with pytest.raises(NotFoundError):
        watchlist.add_entry(session, 999, WatchEntryCreate(anime_id=anime.id))
    with pytest.raises(NotFoundError):
        watchlist.add_entry(session, 1, WatchEntryCreate(anime_id=999))


def test_watchlist_update_requires_payload(session: Session, anime, user) -> None:
    entry = watchlist.add_entry(session, user.id, WatchEntryCreate(anime_id=anime.id))
    with pytest.raises(ValidationAppError):
        watchlist.update_entry(session, entry.id, WatchEntryUpdate())


def test_watchlist_delete_and_list(session: Session, anime, user) -> None:
    entry = watchlist.add_entry(session, user.id, WatchEntryCreate(anime_id=anime.id))
    entries, total = watchlist.list_entries(session, user.id)
    assert total == 1 and entries[0].id == entry.id
    filtered, _ = watchlist.list_entries(session, user.id, status="completed")
    assert filtered == []
    watchlist.delete_entry(session, entry.id)
    assert watchlist.list_entries(session, user.id)[1] == 0


def test_review_requires_completed_status(session: Session, anime, user) -> None:
    with pytest.raises(ConflictError, match="Сначала добавьте"):
        reviews.create_review(session, user.id, anime.id, ReviewCreate(rating=9))
    entry = watchlist.add_entry(
        session, user.id, WatchEntryCreate(anime_id=anime.id, status="watching", progress=1)
    )
    with pytest.raises(ConflictError, match="completed"):
        reviews.create_review(session, user.id, anime.id, ReviewCreate(rating=9))
    watchlist.update_entry(session, entry.id, WatchEntryUpdate(progress=37))
    review = reviews.create_review(session, user.id, anime.id, ReviewCreate(rating=9, body="Ок"))
    assert review.rating == 9


def test_review_unique_per_user(session: Session, anime, user) -> None:
    watchlist.add_entry(
        session, user.id, WatchEntryCreate(anime_id=anime.id, status="completed", progress=37)
    )
    reviews.create_review(session, user.id, anime.id, ReviewCreate(rating=9))
    with pytest.raises(ConflictError, match="уже оставили"):
        reviews.create_review(session, user.id, anime.id, ReviewCreate(rating=8))


def test_review_unknown_entities(session: Session, anime, user) -> None:
    with pytest.raises(NotFoundError):
        reviews.create_review(session, 999, anime.id, ReviewCreate(rating=5))
    with pytest.raises(NotFoundError):
        reviews.create_review(session, user.id, 999, ReviewCreate(rating=5))
    with pytest.raises(NotFoundError):
        reviews.list_reviews(session, 999)


def test_review_list_and_delete(session: Session, anime, user, second_user) -> None:
    for owner, rating in ((user, 9), (second_user, 7)):
        watchlist.add_entry(
            session, owner.id, WatchEntryCreate(anime_id=anime.id, status="completed", progress=37)
        )
        reviews.create_review(session, owner.id, anime.id, ReviewCreate(rating=rating))
    items, total = reviews.list_reviews(session, anime.id)
    assert total == 2
    reviews.delete_review(session, items[0].id)
    assert reviews.list_reviews(session, anime.id)[1] == 1


def test_analytics_top_anime_and_genres(
    session: Session, anime, studio, genres, user, second_user
) -> None:
    second = catalog.create_anime(
        session, AnimeCreate(title="Weak", episodes=12, genre_ids=[genres[0].id])
    )
    for owner, item, rating in ((user, anime, 10), (second_user, anime, 9), (user, second, 4)):
        watchlist.add_entry(
            session,
            owner.id,
            WatchEntryCreate(anime_id=item.id, status="completed", progress=item.episodes or 1),
        )
        reviews.create_review(session, owner.id, item.id, ReviewCreate(rating=rating))
    top = analytics.top_anime(session, limit=2, min_reviews=1)
    assert top[0].title == "Death Note"
    assert top[0].rating_avg == 9.5
    assert top[0].reviews_count == 2

    only_two = analytics.top_anime(session, limit=5, min_reviews=2)
    assert [item.title for item in only_two] == ["Death Note"]

    stats = analytics.genre_stats(session, limit=5)
    action = next(item for item in stats if item.genre == "Action")
    assert action.anime_count == 2
    assert action.avg_rating == pytest.approx(7.67, rel=1e-2)


def test_analytics_year_stats(session: Session, studio) -> None:
    catalog.create_anime(
        session, AnimeCreate(title="A", year=2001, episodes=10, studio_id=studio.id)
    )
    catalog.create_anime(
        session, AnimeCreate(title="B", year=2001, episodes=5, studio_id=studio.id)
    )
    catalog.create_anime(
        session, AnimeCreate(title="C", year=2005, episodes=3, studio_id=studio.id)
    )
    catalog.create_anime(session, AnimeCreate(title="No year"))
    stats = analytics.year_stats(session)
    assert [(item.year, item.titles, item.episodes_total) for item in stats] == [
        (2001, 2, 15),
        (2005, 1, 3),
    ]
    assert [item.year for item in analytics.year_stats(session, year_from=2003)] == [2005]


def test_models_reject_negative_progress_directly(session: Session, anime, user) -> None:
    """CHECK-ограничение в БД дублирует правило сервиса (защита в глубину)."""
    from sqlalchemy.exc import IntegrityError

    session.add(WatchEntry(user_id=user.id, anime_id=anime.id, status="planned", progress=-1))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_anime_status_check_constraint(session: Session) -> None:
    from sqlalchemy.exc import IntegrityError

    session.add(Anime(title="Broken", status="unknown"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


def test_user_duplicate_email(session: Session, user: User) -> None:
    from sqlalchemy.exc import IntegrityError

    session.add(User(email=user.email, username="other"))
    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()
