"""User-facing CLI for the optional semantic anime search."""

import csv
import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from research_graph.embedding import SentenceEncoder
from research_graph.semantic_search import (
    build_index,
    read_catalog,
    read_index_info,
    search_index,
    validate_query,
)

app = typer.Typer(no_args_is_help=True, help="Find anime by a free-form plot description.")
DEFAULT_INDEX = Path("data/processed/anime_search.db")


@app.command("index")
def index_command(
    source: Annotated[Path, typer.Argument(exists=True, dir_okay=False, readable=True)],
    output: Annotated[
        Path, typer.Option("--output", "-o", help="Separate search index database.")
    ] = (DEFAULT_INDEX),
    batch_size: Annotated[int, typer.Option(min=1, max=512)] = 32,
) -> None:
    """Encode a CSV catalog and atomically build/rebuild its SQLite index."""
    try:
        catalog = read_catalog(source)
        typer.echo(
            f"Usable: {len(catalog.records)}; skipped: {catalog.skipped}; duplicates: {catalog.duplicates}"
        )
        typer.echo("Loading multilingual model (first run needs Internet). Indexing on CPU...")
        info = build_index(catalog.records, output, SentenceEncoder(), batch_size=batch_size)
    except (OSError, ValueError, RuntimeError, sqlite3.Error, csv.Error) as error:
        typer.echo(f"Indexing failed: {error}", err=True)
        raise typer.Exit(code=2) from None
    typer.echo(f"Indexed {info.count} titles, {info.dimension} dimensions -> {output}")


@app.command("search")
def search_command(
    description: Annotated[
        str, typer.Argument(help="Description in Russian or another supported language.")
    ],
    index: Annotated[Path, typer.Option("--index", "-i")] = DEFAULT_INDEX,
    top_k: Annotated[int, typer.Option("--top-k", "-k", min=1, max=50)] = 5,
    json_output: Annotated[bool, typer.Option("--json", help="Machine-readable results.")] = False,
) -> None:
    """Return closest candidates. Cosine is similarity, not confidence/probability."""
    try:
        description = validate_query(description)
        # Fail early on a wrong path, before downloading/loading a model.
        if not index.is_file():
            raise ValueError("Index not found. Run 'rg anime index <catalog.csv>' first.")
        read_index_info(index)
        results = search_index(index, description, SentenceEncoder(), top_k=top_k)
    except (OSError, ValueError, RuntimeError, sqlite3.Error, csv.Error) as error:
        typer.echo(f"Search failed: {error}", err=True)
        raise typer.Exit(code=2) from None
    if json_output:
        typer.echo(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
        return
    typer.echo("Nearest candidates (cosine similarity is not a probability):")
    for rank, hit in enumerate(results, start=1):
        typer.echo(f"{rank}. {hit.anime.title} [id={hit.anime.id}; cosine={hit.score:.4f}]")
        typer.echo(f"   {hit.anime.synopsis[:350]}")
