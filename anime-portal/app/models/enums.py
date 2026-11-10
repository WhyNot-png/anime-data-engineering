"""Доменные перечисления. В БД хранятся строками с CHECK-ограничениями."""

from enum import StrEnum


class AnimeStatus(StrEnum):
    UPCOMING = "upcoming"
    AIRING = "airing"
    FINISHED = "finished"


class WatchStatus(StrEnum):
    PLANNED = "planned"
    WATCHING = "watching"
    COMPLETED = "completed"
    DROPPED = "dropped"


ANIME_STATUS_VALUES = tuple(status.value for status in AnimeStatus)
WATCH_STATUS_VALUES = tuple(status.value for status in WatchStatus)
