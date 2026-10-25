from pathlib import Path

import pytest

from research_graph.pipelines.transform import normalize_column, transform


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("English Title", "english_title"),
        ("Score / Rating", "score_rating"),
        ("  MEMBERS!!  ", "members"),
        ("", ""),
    ],
)
def test_normalize_column(source: str, expected: str) -> None:
    assert normalize_column(source) == expected


def test_missing_csv(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="CSV"):
        transform(tmp_path)
