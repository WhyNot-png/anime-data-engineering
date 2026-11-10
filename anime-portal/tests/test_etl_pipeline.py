"""Тесты ETL-пайплайна: идемпотентность, отчёт и CLI."""

import json
from pathlib import Path

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.etl import import_anime
from app.models.anime import Anime
from app.models.genre import Genre
from app.models.studio import Studio

CSV = """mal_id,title,title_english,synopsis,genres,studio,year,episodes,status
1,Cowboy Bebop,Cowboy Bebop,Охотники за головами.,Action;Sci-Fi,Sunrise,1998,26,Finished Airing
2,Steins;Gate,Steins;Gate,Тайм-луп.,Sci-Fi,White Fox,2011,24,Finished Airing
3,,,Пустое название.,Action,,2010,12,Finished Airing
4,Bad Year,Bad Year,Год вне диапазона.,Action,,1800,12,Finished Airing
1,Duplicate,Duplicate,Дубликат.,Action,,1998,26,Finished Airing
"""


@pytest.fixture
def etl_csv(tmp_path: Path) -> Path:
    path = tmp_path / "anime.csv"
    path.write_text(CSV, encoding="utf-8")
    return path


@pytest.fixture
def patched_session(engine: Engine, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(import_anime, "SessionLocal", sessionmaker(bind=engine))


def test_run_reports_counts_and_writes_json(
    etl_csv: Path, patched_session: None, tmp_path: Path
) -> None:
    report_path = tmp_path / "logs" / "etl.json"
    summary = import_anime.run(etl_csv, report_path=report_path)

    assert summary["rows_in_file"] == 5
    assert summary["accepted"] == 2
    assert summary["rejected"] == 2
    assert summary["duplicates_skipped"] == 1
    assert summary["created"] == 2
    assert summary["rejection_reasons"] == {"missing_title": 1, "out_of_range": 1}

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved["accepted"] == 2
    assert len(saved["rejections"]) == 2
    assert saved["db_totals"]["anime"] == 2


def test_second_run_is_idempotent(etl_csv: Path, patched_session: None, engine: Engine) -> None:
    first = import_anime.run(etl_csv)
    second = import_anime.run(etl_csv)

    assert (first["created"], first["updated"]) == (2, 0)
    assert (second["created"], second["updated"]) == (0, 2)
    with Session(engine) as session:
        assert session.scalar(select(func.count(Anime.id))) == 2
        assert session.scalar(select(func.count(Studio.id))) == 2
        assert session.scalar(select(func.count(Genre.id))) == 2


def test_cli_returns_error_for_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert import_anime.main(["--source", str(tmp_path / "nope.csv")]) == 2


def test_cli_rejects_csv_without_title(etl_csv: Path, tmp_path: Path) -> None:
    broken = tmp_path / "broken.csv"
    broken.write_text("mal_id,synopsis\n1,text\n", encoding="utf-8")
    assert import_anime.main(["--source", str(broken)]) == 2


def test_cli_success_path(etl_csv: Path, patched_session: None, tmp_path: Path) -> None:
    report = tmp_path / "report.json"
    assert import_anime.main(["--source", str(etl_csv), "--report", str(report)]) == 0
    assert report.is_file()


def test_demo_csv_is_clean(project_root: Path) -> None:
    from app.etl.cleaning import clean_rows, read_csv

    rows = read_csv(str(project_root / "data" / "anime.csv"))
    report = clean_rows(rows)
    assert len(report.accepted) >= 10
    assert report.duplicates >= 1
    assert report.rejected
