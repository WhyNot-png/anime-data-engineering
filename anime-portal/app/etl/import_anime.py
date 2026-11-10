"""CLI-импорт каталога: python -m app.etl.import_anime --source data/anime.csv.

Идемпотентность: повторный запуск обновляет существующие тайтлы по mal_id
(или по названию, если mal_id нет) и не создаёт дубликатов.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import setup_logging
from app.db import SessionLocal
from app.etl.cleaning import CleanAnime, CleaningReport, clean_rows, read_csv
from app.models.anime import Anime
from app.models.genre import Genre
from app.models.studio import Studio

logger = logging.getLogger("anime_portal.etl")


def _genre(name: str, cache: dict[str, Genre], session: Session) -> Genre:
    if name not in cache:
        existing = session.scalar(select(Genre).where(Genre.name == name))
        if existing is None:
            existing = Genre(name=name, slug=name.lower().replace(" ", "-"))
            session.add(existing)
            session.flush()
        cache[name] = existing
    return cache[name]


def _studio(name: str | None, cache: dict[str, Studio], session: Session) -> Studio | None:
    if not name:
        return None
    if name not in cache:
        existing = session.scalar(select(Studio).where(Studio.name == name))
        if existing is None:
            existing = Studio(name=name)
            session.add(existing)
            session.flush()
        cache[name] = existing
    return cache[name]


def load(session: Session, items: list[CleanAnime]) -> tuple[int, int]:
    """Возвращает (создано, обновлено). Работает в одной транзакции."""
    created = updated = 0
    genre_cache: dict[str, Genre] = {}
    studio_cache: dict[str, Studio] = {}
    for item in items:
        anime = None
        if item.mal_id is not None:
            anime = session.scalar(select(Anime).where(Anime.mal_id == item.mal_id))
        if anime is None:
            anime = session.scalar(select(Anime).where(Anime.title == item.title))
        if anime is None:
            anime = Anime(title=item.title)
            session.add(anime)
            created += 1
        else:
            updated += 1
        anime.mal_id = item.mal_id
        anime.title = item.title
        anime.title_english = item.title_english
        anime.synopsis = item.synopsis
        anime.year = item.year
        anime.episodes = item.episodes
        anime.status = item.status
        anime.studio = _studio(item.studio, studio_cache, session)
        anime.genres = [_genre(name, genre_cache, session) for name in item.genres]
        session.flush()
    session.commit()
    return created, updated


def run(source: Path, *, report_path: Path | None = None) -> dict[str, object]:
    rows = read_csv(str(source))
    report: CleaningReport = clean_rows(rows)
    with SessionLocal() as session:
        created, updated = load(session, report.accepted)
        total_anime = session.scalar(select(func.count(Anime.id))) or 0
        total_studios = session.scalar(select(func.count(Studio.id))) or 0
        total_genres = session.scalar(select(func.count(Genre.id))) or 0
    reasons: dict[str, int] = {}
    for rejection in report.rejected:
        reasons[rejection.reason] = reasons.get(rejection.reason, 0) + 1
    summary: dict[str, object] = {
        "source": str(source),
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "rows_in_file": report.total_rows,
        "accepted": len(report.accepted),
        "rejected": len(report.rejected),
        "duplicates_skipped": report.duplicates,
        "created": created,
        "updated": updated,
        "rejection_reasons": reasons,
        "rejections": [
            {"row": item.row, "reason": item.reason, "detail": item.detail}
            for item in report.rejected
        ],
        "db_totals": {
            "anime": total_anime,
            "studios": total_studios,
            "genres": total_genres,
        },
    }
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Импорт каталога аниме из CSV в БД.")
    parser.add_argument("--source", required=True, type=Path, help="Путь к CSV-файлу")
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("logs/etl-report.json"),
        help="Куда сохранить JSON-отчёт о запуске",
    )
    args = parser.parse_args(argv)
    setup_logging()
    if not args.source.is_file():
        logger.error("Файл не найден: %s", args.source)
        return 2
    try:
        summary = run(args.source, report_path=args.report)
    except ValueError as error:
        logger.error("Импорт прерван: %s", error)
        return 2
    logger.info(
        "Импорт завершён: принято %s, отклонено %s, дубликатов %s, создано %s, обновлено %s",
        summary["accepted"],
        summary["rejected"],
        summary["duplicates_skipped"],
        summary["created"],
        summary["updated"],
    )
    rejection_reasons = cast(dict[str, int], summary["rejection_reasons"])
    for reason, count in rejection_reasons.items():
        logger.warning("Причина отказа %s: %s строк", reason, count)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
