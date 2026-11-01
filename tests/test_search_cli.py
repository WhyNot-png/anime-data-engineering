"""End-to-end CLI tests use a fake encoder and local tiny CSV."""

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Literal

import pytest
from typer.testing import CliRunner

from research_graph import search_cli
from research_graph.cli import app

runner = CliRunner()


class Encoder:
    model_name = "cli-test"
    revision = "v1"

    def encode(
        self, texts: Sequence[str], *, kind: Literal["query", "passage"]
    ) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def test_index_search_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(search_cli, "SentenceEncoder", Encoder)
    source = tmp_path / "anime.csv"
    source.write_text("mal_id,title,synopsis\n1,Example,A story about space\n", encoding="utf-8")
    index = tmp_path / "index.db"
    result = runner.invoke(app, ["anime", "index", str(source), "-o", str(index)])
    assert result.exit_code == 0, result.output
    assert "Indexed 1 titles" in result.output
    result = runner.invoke(app, ["anime", "search", "космос", "-i", str(index), "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload[0]["anime"]["title"] == "Example"
    assert payload[0]["score"] == pytest.approx(1.0)
    result = runner.invoke(app, ["anime", "search", "космос", "-i", str(index)])
    assert result.exit_code == 0
    assert "not a probability" in result.output
    assert "Example" in result.output


def test_bad_input_without_model_download(tmp_path: Path) -> None:
    result = runner.invoke(app, ["anime", "search", "query", "-i", str(tmp_path / "absent.db")])
    assert result.exit_code == 2 and "Index not found" in result.output
    result = runner.invoke(app, ["anime", "search", "   "])
    assert result.exit_code == 2 and "Description must" in result.output
    source = tmp_path / "bad.csv"
    source.write_text("title,score\nNo synopsis,9\n")
    result = runner.invoke(app, ["anime", "index", str(source)])
    assert result.exit_code == 2 and "CSV needs" in result.output
