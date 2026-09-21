from src.transform import normalize_column


def test_normalize_column() -> None:
    assert normalize_column("English Title") == "english_title"
    assert normalize_column("Score / Rating") == "score_rating"
