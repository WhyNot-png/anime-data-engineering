"""Наполнение БД демо-данными поверх ETL-импорта.

Запуск: python scripts/seed.py [--source data/anime.csv]
Идемпотентен: повторный запуск не создаёт дубликатов.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.etl.import_anime import run as run_etl  # noqa: E402
from app.models.anime import Anime  # noqa: E402
from app.models.review import Review  # noqa: E402
from app.models.user import User  # noqa: E402
from app.models.watch import WatchEntry  # noqa: E402

DEMO_USERS = [
    ("sakura@example.com", "sakura"),
    ("kenji@example.com", "kenji"),
    ("mika@example.com", "mika"),
]

DEMO_WATCH = {
    "sakura": [
        ("Death Note", "completed", 37),
        ("Steins;Gate", "completed", 24),
        ("Frieren", "watching", 10),
    ],
    "kenji": [("Death Note", "completed", 37), ("One Piece", "watching", 300)],
    "mika": [("Steins;Gate", "completed", 24), ("Frieren", "completed", 28)],
}

DEMO_REVIEWS = {
    ("sakura", "Death Note"): (9, "Первая половина держит в напряжении до конца."),
    ("sakura", "Steins;Gate"): (10, "Лучший тайм-луп, который я видел."),
    ("kenji", "Death Note"): (8, "Вторая половина слабее, но всё равно мощно."),
    ("mika", "Steins;Gate"): (9, "Медленный старт, но награда того стоит."),
    ("mika", "Frieren"): (10, "Тихая, грустная и очень красивая история."),
}


def seed() -> dict[str, int]:
    created_users = created_entries = created_reviews = 0
    with SessionLocal() as session:
        users: dict[str, User] = {}
        for email, username in DEMO_USERS:
            user = session.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(email=email, username=username)
                session.add(user)
                session.flush()
                created_users += 1
            users[username] = user
        for username, entries in DEMO_WATCH.items():
            for title, status, progress in entries:
                anime = session.scalar(select(Anime).where(Anime.title.like(f"{title}%")))
                if anime is None:
                    continue
                exists = session.scalar(
                    select(WatchEntry.id).where(
                        WatchEntry.user_id == users[username].id,
                        WatchEntry.anime_id == anime.id,
                    )
                )
                if exists is None:
                    session.add(
                        WatchEntry(
                            user_id=users[username].id,
                            anime_id=anime.id,
                            status=status,
                            progress=progress,
                        )
                    )
                    created_entries += 1
        for (username, title), (rating, body) in DEMO_REVIEWS.items():
            anime = session.scalar(select(Anime).where(Anime.title.like(f"{title}%")))
            if anime is None:
                continue
            exists = session.scalar(
                select(Review.id).where(
                    Review.user_id == users[username].id, Review.anime_id == anime.id
                )
            )
            if exists is None:
                session.add(
                    Review(
                        user_id=users[username].id,
                        anime_id=anime.id,
                        rating=rating,
                        body=body,
                    )
                )
                created_reviews += 1
        session.commit()
    return {
        "users": created_users,
        "watch_entries": created_entries,
        "reviews": created_reviews,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Демо-данные Anime Portal")
    parser.add_argument("--source", type=Path, default=Path("data/anime.csv"))
    parser.add_argument("--skip-etl", action="store_true", help="Только пользователи и отзывы")
    args = parser.parse_args()
    if not args.skip_etl:
        summary = run_etl(args.source)
        print(f"ETL: принято {summary['accepted']}, отклонено {summary['rejected']}")
    print("Seed:", seed())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
