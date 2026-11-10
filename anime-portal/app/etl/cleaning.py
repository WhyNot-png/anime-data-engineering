"""Чистые функции очистки и валидации строк CSV.

Вынесены отдельно от загрузки в БД, чтобы их можно было покрыть unit-тестами
без базы данных и без файловой системы.
"""

from __future__ import annotations

import csv
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.models.enums import ANIME_STATUS_VALUES

STATUS_ALIASES = {
    "finished": "finished",
    "finished airing": "finished",
    "complete": "finished",
    "completed": "finished",
    "airing": "airing",
    "currently airing": "airing",
    "ongoing": "airing",
    "upcoming": "upcoming",
    "not yet aired": "upcoming",
}

GENRE_SPLIT = re.compile(r"[;|,]")
SPACES = re.compile(r"\s+")

REQUIRED_COLUMNS = ("title",)


class RowRejected(Exception):
    """Строка не может быть загружена; текст исключения — причина отказа."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


@dataclass(frozen=True)
class CleanAnime:
    mal_id: int | None
    title: str
    title_english: str | None
    synopsis: str | None
    year: int | None
    episodes: int | None
    status: str
    studio: str | None
    genres: tuple[str, ...]


@dataclass
class Rejection:
    row: int
    reason: str
    detail: str


@dataclass
class CleaningReport:
    accepted: list[CleanAnime] = field(default_factory=list)
    rejected: list[Rejection] = field(default_factory=list)
    duplicates: int = 0

    @property
    def total_rows(self) -> int:
        return len(self.accepted) + len(self.rejected) + self.duplicates


def clean_text(value: str | None) -> str:
    return SPACES.sub(" ", (value or "").replace("\ufeff", " ")).strip()


def parse_int(value: str | None, *, field_name: str, minimum: int, maximum: int) -> int | None:
    text = clean_text(value)
    if not text:
        return None
    try:
        number = int(text)
    except ValueError as error:
        raise RowRejected("bad_number", f"{field_name}={text!r} не целое число") from error
    if not minimum <= number <= maximum:
        raise RowRejected("out_of_range", f"{field_name}={number} вне {minimum}..{maximum}")
    return number


def normalize_status(value: str | None) -> str:
    text = clean_text(value).lower()
    if not text:
        return "finished"
    if text in STATUS_ALIASES:
        return STATUS_ALIASES[text]
    if text in ANIME_STATUS_VALUES:
        return text
    raise RowRejected("bad_status", f"неизвестный статус {value!r}")


def split_genres(value: str | None) -> tuple[str, ...]:
    names = {
        clean_text(part).title() for part in GENRE_SPLIT.split(value or "") if clean_text(part)
    }
    return tuple(sorted(names))


def clean_row(row: dict[str, str]) -> CleanAnime:
    """Преобразует строку CSV в CleanAnime или выбрасывает RowRejected."""
    title = clean_text(row.get("title"))
    if not title:
        raise RowRejected("missing_title", "пустое название")
    if len(title) > 300:
        raise RowRejected("title_too_long", f"длина названия {len(title)} > 300")
    synopsis = clean_text(row.get("synopsis")) or None
    if synopsis and len(synopsis) > 4000:
        synopsis = synopsis[:4000]
    return CleanAnime(
        mal_id=parse_int(row.get("mal_id"), field_name="mal_id", minimum=1, maximum=10**9),
        title=title,
        title_english=clean_text(row.get("title_english")) or None,
        synopsis=synopsis,
        year=parse_int(row.get("year"), field_name="year", minimum=1900, maximum=2100),
        episodes=parse_int(row.get("episodes"), field_name="episodes", minimum=0, maximum=10000),
        status=normalize_status(row.get("status")),
        studio=clean_text(row.get("studio")) or None,
        genres=split_genres(row.get("genres")),
    )


def clean_rows(rows: list[dict[str, str]], *, key_field: str = "mal_id") -> CleaningReport:
    """Очищает все строки, отбрасывая дубликаты по mal_id, иначе по названию."""
    report = CleaningReport()
    seen: set[object] = set()
    for index, row in enumerate(rows, start=2):
        try:
            anime = clean_row(row)
        except RowRejected as rejection:
            report.rejected.append(Rejection(index, rejection.reason, rejection.detail))
            continue
        key: object = anime.mal_id if anime.mal_id is not None else anime.title.casefold()
        if key in seen:
            report.duplicates += 1
            continue
        seen.add(key)
        report.accepted.append(anime)
    return report


def validate_header(fieldnames: Sequence[str] | None) -> None:
    if not fieldnames:
        raise ValueError("CSV пуст или без заголовка.")
    missing = [name for name in REQUIRED_COLUMNS if name not in fieldnames]
    if missing:
        raise ValueError(f"В CSV нет обязательных колонок: {missing}")


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        validate_header(reader.fieldnames)
        return [dict(row) for row in reader]
