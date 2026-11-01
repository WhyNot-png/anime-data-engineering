"""Offline catalog indexing and exact cosine search in a separate SQLite database.

The core deliberately uses only the standard library. Embeddings are supplied by
an Encoder, so tests do not download models or require network access.
"""

import csv
import hashlib
import heapq
import html
import math
import re
import sqlite3
import struct
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol, cast

from research_graph.pipelines.transform import normalize_column

SCHEMA_VERSION = 1
MAX_QUERY_LENGTH = 4000


@dataclass(frozen=True)
class Anime:
    """One searchable title; synopsis is required, other descriptions are optional."""

    id: str
    title: str
    synopsis: str
    genres: str = ""
    themes: str = ""

    @property
    def document(self) -> str:
        return f"{self.title}. {self.genres}. {self.themes}. {self.synopsis}"


@dataclass(frozen=True)
class Catalog:
    records: tuple[Anime, ...]
    skipped: int
    duplicates: int


@dataclass(frozen=True)
class IndexInfo:
    model_name: str
    revision: str
    dimension: int
    count: int


@dataclass(frozen=True)
class Hit:
    anime: Anime
    score: float


class Encoder(Protocol):
    @property
    def model_name(self) -> str: ...

    @property
    def revision(self) -> str: ...

    def encode(
        self, texts: Sequence[str], *, kind: Literal["query", "passage"]
    ) -> list[list[float]]: ...


def _clean(value: str | None) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<[^>]*>", " ", text)
    return " ".join(text.split())


def _missing_synopsis(text: str) -> bool:
    return text.casefold() in {
        "",
        "nan",
        "null",
        "none",
        "n/a",
        "unknown",
    } or text.casefold().startswith(
        ("no synopsis information", "no synopsis available", "no description available")
    )


def read_catalog(path: Path) -> Catalog:
    """Read MAL-like CSV, supporting common aliases and skipping missing synopses.

    Duplicate IDs keep their first usable row. Without an ID, a stable hash of
    title + synopsis is used. No source text is invented for missing synopses.
    """
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, strict=True)
        if not reader.fieldnames:
            raise ValueError("CSV is empty or has no header.")
        normalized = [normalize_column(name) for name in reader.fieldnames]
        if len(set(normalized)) != len(normalized):
            raise ValueError("CSV has ambiguous duplicate column names.")
        columns = dict(zip(normalized, reader.fieldnames, strict=True))

        def column(*aliases: str) -> str | None:
            return next((columns[name] for name in aliases if name in columns), None)

        title_col = column("title", "name", "romaji_title", "title_english", "english_name")
        synopsis_col = column("synopsis", "description", "summary", "sypnopsis")
        if title_col is None or synopsis_col is None:
            raise ValueError("CSV needs title/name and synopsis/description columns.")
        id_col = column("mal_id", "anime_id", "id", "uid")
        genres_col = column("genres", "genre")
        themes_col = column("themes", "theme")
        records: list[Anime] = []
        seen: set[str] = set()
        skipped = duplicates = 0
        for line, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"CSV row {line} has more fields than the header.")
            title = _clean(row.get(title_col))
            synopsis = _clean(row.get(synopsis_col))
            if not title or _missing_synopsis(synopsis):
                skipped += 1
                continue
            identifier = _clean(row.get(id_col)) if id_col else ""
            if not identifier:
                identifier = hashlib.sha256(f"{title}\0{synopsis}".encode()).hexdigest()[:24]
            if identifier in seen:
                duplicates += 1
                continue
            seen.add(identifier)
            records.append(
                Anime(
                    identifier,
                    title,
                    synopsis,
                    _clean(row.get(genres_col)) if genres_col else "",
                    _clean(row.get(themes_col)) if themes_col else "",
                )
            )
    if not records:
        raise ValueError("CSV contains no usable titles with synopses.")
    return Catalog(tuple(records), skipped, duplicates)


def normalize_vector(vector: Sequence[float], dimension: int | None = None) -> list[float]:
    if not vector or len(vector) > 8192 or (dimension is not None and len(vector) != dimension):
        raise ValueError("Embedding dimension is empty, unsupported or inconsistent.")
    if not all(math.isfinite(value) for value in vector):
        raise ValueError("Embedding contains NaN or infinity.")
    norm = math.hypot(*vector)
    if not norm or not math.isfinite(norm):
        raise ValueError("Embedding has zero or invalid norm.")
    return [value / norm for value in vector]


def build_index(
    records: Sequence[Anime], output: Path, encoder: Encoder, *, batch_size: int = 32
) -> IndexInfo:
    """Build atomically: a failed rebuild never overwrites the previous index."""
    if not records:
        raise ValueError("Cannot index an empty catalog.")
    if not 1 <= batch_size <= 512:
        raise ValueError("Batch size must be between 1 and 512.")
    if output.exists():
        try:
            read_index_info(output)
        except (sqlite3.Error, ValueError) as error:
            raise ValueError(
                "Refusing to overwrite an unrelated/invalid file; choose a new index path."
            ) from error
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=output.parent, suffix=".tmp", delete=False) as stream:
        temporary = Path(stream.name)
    try:
        with closing(sqlite3.connect(temporary)) as connection, connection:
            connection.execute(
                "CREATE TABLE anime (id TEXT PRIMARY KEY, title TEXT NOT NULL, "
                "synopsis TEXT NOT NULL, genres TEXT NOT NULL, themes TEXT NOT NULL, "
                "embedding BLOB NOT NULL)"
            )
            dimension: int | None = None
            for start in range(0, len(records), batch_size):
                batch = records[start : start + batch_size]
                vectors = encoder.encode([record.document for record in batch], kind="passage")
                if len(vectors) != len(batch):
                    raise ValueError("Encoder returned an unexpected number of embeddings.")
                for record, vector in zip(batch, vectors, strict=True):
                    normalized = normalize_vector(vector, dimension)
                    dimension = len(normalized)
                    blob = struct.pack(f"<{dimension}f", *normalized)
                    connection.execute(
                        "INSERT INTO anime VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            record.id,
                            record.title,
                            record.synopsis,
                            record.genres,
                            record.themes,
                            blob,
                        ),
                    )
            assert dimension is not None
            info = IndexInfo(encoder.model_name, encoder.revision, dimension, len(records))
            connection.execute(
                "CREATE TABLE metadata (version INTEGER NOT NULL, model_name TEXT NOT NULL, "
                "revision TEXT NOT NULL, dimension INTEGER NOT NULL, count INTEGER NOT NULL)"
            )
            connection.execute(
                "INSERT INTO metadata VALUES (?, ?, ?, ?, ?)",
                (SCHEMA_VERSION, info.model_name, info.revision, info.dimension, info.count),
            )
        temporary.replace(output)
        return info
    finally:
        temporary.unlink(missing_ok=True)


def _open_index(path: Path) -> sqlite3.Connection:
    # mode=ro is important: a typo must not create an empty database.
    return sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)


def _read_info(connection: sqlite3.Connection) -> IndexInfo:
    rows = connection.execute(
        "SELECT version, model_name, revision, dimension, count FROM metadata"
    ).fetchall()
    if len(rows) != 1:
        raise ValueError("Index metadata is missing or ambiguous; rebuild the index.")
    version, model, revision, dimension, count = rows[0]
    if (
        version != SCHEMA_VERSION
        or not isinstance(model, str)
        or not model
        or not isinstance(revision, str)
        or not revision
        or type(dimension) is not int
        or not 1 <= dimension <= 8192
        or type(count) is not int
        or count < 1
    ):
        raise ValueError("Unsupported or invalid index metadata; rebuild the index.")
    actual_count = connection.execute("SELECT COUNT(*) FROM anime").fetchone()[0]
    if actual_count != count:
        raise ValueError("Index row count does not match its metadata; rebuild the index.")
    return IndexInfo(model, revision, dimension, count)


def read_index_info(path: Path) -> IndexInfo:
    with closing(_open_index(path)) as connection:
        return _read_info(connection)


def validate_query(query: str) -> str:
    query = query.strip()
    if not query or len(query) > MAX_QUERY_LENGTH:
        raise ValueError(f"Description must contain 1 to {MAX_QUERY_LENGTH} characters.")
    return query


def search_index(path: Path, query: str, encoder: Encoder, *, top_k: int = 5) -> list[Hit]:
    """Return exact nearest neighbors. Cosine similarity is NOT a probability."""
    query = validate_query(query)
    if not 1 <= top_k <= 50:
        raise ValueError("top_k must be between 1 and 50.")
    with closing(_open_index(path)) as connection:
        info = _read_info(connection)
        if (encoder.model_name, encoder.revision) != (info.model_name, info.revision):
            raise ValueError("Query model/revision differs from the index; rebuild the index.")
        query_vectors = encoder.encode([query], kind="query")
        if len(query_vectors) != 1:
            raise ValueError("Encoder must return exactly one query embedding.")
        query_vector = normalize_vector(query_vectors[0], info.dimension)
        cursor = connection.execute(
            "SELECT id, title, synopsis, genres, themes, embedding FROM anime"
        )

        def hits() -> list[Hit]:
            # nlargest keeps only top_k candidates, not all vectors/results in RAM.
            def candidates() -> Iterator[Hit]:
                for row in cursor:
                    identifier, title, synopsis, genres, themes, blob = cast(
                        tuple[str, str, str, str, str, bytes], row
                    )
                    if not isinstance(blob, bytes) or len(blob) != 4 * info.dimension:
                        raise ValueError("Index contains a malformed embedding; rebuild it.")
                    vector = struct.unpack(f"<{info.dimension}f", blob)
                    if not all(math.isfinite(value) for value in vector):
                        raise ValueError("Index contains a non-finite embedding; rebuild it.")
                    score = math.fsum(a * b for a, b in zip(query_vector, vector, strict=True))
                    yield Hit(
                        Anime(identifier, title, synopsis, genres, themes), max(-1, min(1, score))
                    )

            return heapq.nlargest(top_k, candidates(), key=lambda hit: (hit.score, hit.anime.id))

        return hits()
