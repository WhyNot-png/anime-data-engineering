"""SQLAlchemy-модели. Импортируйте этот модуль, чтобы все таблицы попали в metadata."""

from app.models.anime import Anime, anime_genres
from app.models.genre import Genre
from app.models.review import Review
from app.models.studio import Studio
from app.models.user import User
from app.models.watch import WatchEntry

__all__ = ["Anime", "Genre", "Review", "Studio", "User", "WatchEntry", "anime_genres"]
