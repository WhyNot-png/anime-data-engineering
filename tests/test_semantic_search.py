"""No network or model downloads: test storage/search with a deterministic encoder."""

import csv
import sqlite3
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pytest

from research_graph.semantic_search import (
    Anime,
    build_index,
    normalize_vector,
    read_catalog,
    read_index_info,
    search_index,
    validate_query,
)


class FakeEncoder:
    model_name = "test-model"
    revision = "test-revision"

    def encode(
        self, texts: Sequence[str], *, kind: Literal["query", "passage"]
    ) -> list[list[float]]:
        assert kind in {"query", "passage"}
        return [
            [3.0, 0.0] if "notebook" in text.lower() or "тетрад" in text.lower() else [0.0, 5.0]
            for text in texts
        ]


def catalog() -> tuple[Anime, ...]:
    return (
        Anime("1535", "Death Note", "A supernatural notebook kills people.", "Supernatural"),
        Anime("21", "One Piece", "Pirates sail the ocean to find a treasure.", "Adventure"),
    )


def test_csv_aliases_skips_and_deduplicates(tmp_path: Path) -> None:
    source = tmp_path / "anime.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["MAL ID", "Name", "Description", "Genre", "Theme"])
        writer.writerows(
            [
                ["1", "Test", "First<br>plot &amp; story", "Action", "School"],
                ["1", "Duplicate", "Another description", "", ""],
                ["2", "Empty", "", "", ""],
                ["3", "Missing", "No synopsis information has been added to this title.", "", ""],
                ["", "Other", "Other plot", "", ""],
                ["", "Other", "Other plot", "", ""],
                ["4", "", "Description", "", ""],
            ]
        )
    result = read_catalog(source)
    assert len(result.records) == 2
    assert result.skipped == 3
    assert result.duplicates == 2
    assert result.records[0].synopsis == "First plot & story"
    assert "School" in result.records[0].document
    assert len(result.records[1].id) == 24


@pytest.mark.parametrize(
    "content",
    [
        "",
        "title,score\nX,9\n",
        "title,synopsis\nX,unknown\n",
        "Title,title,synopsis\nX,Y,z\n",
        "title,synopsis\nX,Y,Z\n",
    ],
)
def test_invalid_catalog(tmp_path: Path, content: str) -> None:
    source = tmp_path / "bad.csv"
    source.write_text(content)
    with pytest.raises(ValueError):
        read_catalog(source)


def test_normalized_vectors_and_exact_top_k(tmp_path: Path) -> None:
    index = tmp_path / "nested" / "search.db"
    info = build_index(catalog(), index, FakeEncoder(), batch_size=1)
    assert info.count == 2 and info.dimension == 2
    assert read_index_info(index) == info
    hits = search_index(index, "  тетрадь убивает людей  ", FakeEncoder(), top_k=1)
    assert hits[0].anime.title == "Death Note"
    assert hits[0].score == pytest.approx(1.0)
    assert len(search_index(index, "pirates", FakeEncoder(), top_k=50)) == 2
    assert search_index(index, "pirates", FakeEncoder())[0].anime.title == "One Piece"


@pytest.mark.parametrize("vector", [[], [0.0, 0.0], [float("nan")], [float("inf")]])
def test_reject_invalid_vectors(vector: list[float]) -> None:
    with pytest.raises(ValueError):
        normalize_vector(vector)
    with pytest.raises(ValueError):
        normalize_vector([1.0, 0.0], 3)


def test_invalid_build_and_queries(tmp_path: Path) -> None:
    path = tmp_path / "search.db"
    with pytest.raises(ValueError):
        build_index([], path, FakeEncoder())
    with pytest.raises(ValueError):
        build_index(catalog(), path, FakeEncoder(), batch_size=0)
    with pytest.raises(sqlite3.OperationalError):
        read_index_info(path)
    assert not path.exists()
    build_index(catalog(), path, FakeEncoder())
    for value in ["", "  ", "x" * 4001]:
        with pytest.raises(ValueError):
            search_index(path, value, FakeEncoder())
    with pytest.raises(ValueError):
        search_index(path, "valid", FakeEncoder(), top_k=0)
    assert validate_query(" trimmed ") == "trimmed"


def test_model_mismatch(tmp_path: Path) -> None:
    path = tmp_path / "search.db"
    encoder = FakeEncoder()
    build_index(catalog(), path, encoder)
    encoder.revision = "different"
    with pytest.raises(ValueError, match="differs"):
        search_index(path, "query", encoder)


class BrokenEncoder(FakeEncoder):
    def encode(
        self, texts: Sequence[str], *, kind: Literal["query", "passage"]
    ) -> list[list[float]]:
        return []


def test_atomic_rebuild_keeps_previous_index(tmp_path: Path) -> None:
    path = tmp_path / "search.db"
    build_index(catalog(), path, FakeEncoder())
    original = path.read_bytes()
    with pytest.raises(ValueError, match="number"):
        build_index(catalog(), path, BrokenEncoder())
    assert path.read_bytes() == original
    assert not list(tmp_path.glob("*.tmp"))
    with pytest.raises(ValueError, match="exactly one"):
        search_index(path, "query", BrokenEncoder())
    build_index(catalog()[:1], path, FakeEncoder())
    assert read_index_info(path).count == 1


def test_does_not_overwrite_unrelated_file(tmp_path: Path) -> None:
    path = tmp_path / "source.csv"
    path.write_text("important source data")
    with pytest.raises(ValueError, match="Refusing"):
        build_index(catalog(), path, FakeEncoder())
    assert path.read_text() == "important source data"


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE metadata SET version=999",
        "UPDATE metadata SET dimension=0",
        "UPDATE metadata SET count=999",
        "DELETE FROM metadata",
        "UPDATE anime SET embedding=x'00'",
        "UPDATE anime SET embedding=x'0000807f0000803f'",
    ],
)
def test_corrupted_index_is_rejected(tmp_path: Path, sql: str) -> None:
    path = tmp_path / "search.db"
    build_index(catalog(), path, FakeEncoder())
    with sqlite3.connect(path) as connection:
        connection.execute(sql)
    with pytest.raises(ValueError):
        search_index(path, "query", FakeEncoder())
