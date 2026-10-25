"""Integration coverage for the existing optional ETL, without Kaggle/network."""

import sqlite3
from pathlib import Path

import pytest

from research_graph.pipelines.load import load
from research_graph.pipelines.transform import transform


def test_csv_parquet_sqlite_roundtrip(tmp_path: Path) -> None:
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "anime.csv").write_text(
        "English Title,Score / Rating\nAnime A,8.5\nAnime A,8.5\nAnime B,7.1\n"
    )
    parquet = transform(raw)
    assert parquet == Path("data/processed/anime_clean.parquet")
    assert load(parquet) == 2
    with sqlite3.connect("data/processed/anime.db") as connection:
        rows = connection.execute(
            "SELECT english_title, score_rating FROM anime ORDER BY 1"
        ).fetchall()
    assert rows == [("Anime A", 8.5), ("Anime B", 7.1)]


def test_largest_csv_and_custom_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "small.csv").write_text("title\nX\n")
    (tmp_path / "large.csv").write_text("English Title\nA very long anime title\n")
    parquet = transform(tmp_path, Path("custom-output"))
    assert parquet == Path("custom-output/anime_clean.parquet")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///custom.db")
    assert load(parquet) == 1
    with sqlite3.connect("custom.db") as connection:
        assert connection.execute("SELECT english_title FROM anime").fetchone() == (
            "A very long anime title",
        )


def test_main_orchestrates_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from research_graph.pipelines import main as pipeline

    raw = tmp_path / "input"
    parquet = tmp_path / "output.parquet"
    calls: list[tuple[Path, Path | None]] = []

    def fake_extract() -> Path:
        return raw

    def fake_transform(source: Path, output: Path | None = None) -> Path:
        calls.append((source, output))
        return parquet

    def fake_load(source: Path) -> int:
        assert source == parquet
        return 2

    monkeypatch.setenv("PROCESSED_DATA_DIR", "custom-processed")
    monkeypatch.setattr(pipeline, "extract", fake_extract)
    monkeypatch.setattr(pipeline, "transform", fake_transform)
    monkeypatch.setattr(pipeline, "load", fake_load)
    pipeline.main()
    assert calls == [(raw, Path("custom-processed"))]
    output = capsys.readouterr()
    assert output.out == ""
    assert "ETL completed: 2 rows loaded" in output.err
