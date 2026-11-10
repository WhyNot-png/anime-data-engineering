"""Unit-тесты очистки данных: обязательны по требованиям задания."""

import pytest

from app.etl.cleaning import (
    RowRejected,
    clean_row,
    clean_rows,
    clean_text,
    normalize_status,
    parse_int,
    split_genres,
    validate_header,
)


def test_clean_text_collapses_spaces_and_bom() -> None:
    assert clean_text("\ufeff  Death   Note \n") == "Death Note"
    assert clean_text(None) == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [("2006", 2006), (" 2006 ", 2006), ("", None), (None, None)],
)
def test_parse_int_accepts_numbers(value: str | None, expected: int | None) -> None:
    assert parse_int(value, field_name="year", minimum=1900, maximum=2100) == expected


def test_parse_int_accepts_zero_episodes() -> None:
    assert parse_int("0", field_name="episodes", minimum=0, maximum=10000) == 0


@pytest.mark.parametrize(("value", "reason"), [("1800", "out_of_range"), ("abc", "bad_number")])
def test_parse_int_rejects_bad_values(value: str, reason: str) -> None:
    with pytest.raises(RowRejected) as error:
        parse_int(value, field_name="year", minimum=1900, maximum=2100)
    assert error.value.reason == reason


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("Finished Airing", "finished"),
        ("Currently Airing", "airing"),
        ("Not yet aired", "upcoming"),
        ("", "finished"),
        ("finished", "finished"),
    ],
)
def test_normalize_status_aliases(value: str, expected: str) -> None:
    assert normalize_status(value) == expected


def test_normalize_status_rejects_unknown() -> None:
    with pytest.raises(RowRejected) as error:
        normalize_status("on hold")
    assert error.value.reason == "bad_status"


def test_split_genres_deduplicates_and_normalizes() -> None:
    assert split_genres("Action; action |Drama, Sci-Fi") == ("Action", "Drama", "Sci-Fi")
    assert split_genres(None) == ()


def test_clean_row_strips_and_limits_synopsis() -> None:
    row = {
        "mal_id": "1",
        "title": "  Cowboy   Bebop ",
        "synopsis": "x" * 5000,
        "year": "1998",
        "episodes": "26",
        "status": "Finished Airing",
        "studio": "Sunrise",
        "genres": "Action;Sci-Fi",
    }
    anime = clean_row(row)
    assert anime.title == "Cowboy Bebop"
    assert anime.synopsis is not None and len(anime.synopsis) == 4000
    assert anime.genres == ("Action", "Sci-Fi")
    assert anime.status == "finished"


def test_clean_row_requires_title() -> None:
    with pytest.raises(RowRejected) as error:
        clean_row({"title": "   ", "year": "2000"})
    assert error.value.reason == "missing_title"


def test_clean_rows_reports_reasons_and_duplicates() -> None:
    rows = [
        {"title": "A", "mal_id": "1"},
        {"title": "A duplicate", "mal_id": "1"},
        {"title": "", "mal_id": "2"},
        {"title": "B", "year": "1800"},
        {"title": "C", "mal_id": "3"},
    ]
    report = clean_rows(rows)
    assert [item.title for item in report.accepted] == ["A", "C"]
    assert report.duplicates == 1
    assert {item.reason for item in report.rejected} == {"missing_title", "out_of_range"}
    assert report.total_rows == 5


def test_validate_header_requires_title_column() -> None:
    validate_header(["title", "mal_id"])
    with pytest.raises(ValueError, match="обязательных колонок"):
        validate_header(["mal_id", "synopsis"])
    with pytest.raises(ValueError, match="пуст"):
        validate_header([])
