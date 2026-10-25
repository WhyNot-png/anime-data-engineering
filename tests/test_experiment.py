"""The scientific stage uses local numeric data, never the Kaggle network."""

import json
from pathlib import Path

import pytest

from scripts import experiment


def sample(path: Path) -> Path:
    path.write_text(
        "mal_id,type,score,scored_by\n1,TV,8.0,1000\n2,TV,,\n3,Movie,7.0,999\n4,TV,6.0,2000\n",
        encoding="utf-8",
    )
    return path


def test_calculation_respects_population_and_denominator(tmp_path: Path) -> None:
    result = experiment.calculate(sample(tmp_path / "data.csv"), {"min_votes": 1000})
    assert result["source_rows"] == 4
    assert result["missing_scores"] == 1
    assert result["eligible"] == 2
    assert result["groups"] == [{"format": "TV", "count": 2, "mean_score": 7.0}]


def test_duplicate_ids_are_rejected(tmp_path: Path) -> None:
    path = sample(tmp_path / "data.csv")
    with path.open("a") as stream:
        stream.write("1,TV,8.0,1000\n")
    with pytest.raises(ValueError, match="Duplicate mal_id"):
        experiment.calculate(path, {"min_votes": 1000})


@pytest.mark.parametrize("score", ["nan", "inf", "-1", "11"])
def test_invalid_score_is_not_silently_treated_as_zero(tmp_path: Path, score: str) -> None:
    path = tmp_path / "invalid.csv"
    path.write_text(f"mal_id,type,score,scored_by\n1,TV,{score},1000\n", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid"):
        experiment.calculate(path, {"min_votes": 1000})


def test_cache_invalidation_and_fresh_build_metadata(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "research").mkdir()
    sample(tmp_path / "research/anime-metrics.csv")
    params = tmp_path / "research/parameters.json"
    params.write_text(
        json.dumps({"min_votes": 1000, "dataset_version": "test-v1"}), encoding="utf-8"
    )
    (tmp_path / "uv.lock").write_text("test-lock", encoding="utf-8")
    monkeypatch.setattr(experiment, "ROOT", tmp_path)
    monkeypatch.setenv("GITHUB_SHA", "commit-one")
    out = tmp_path / "docs/generated/evidence.json"
    experiment.main()
    first = json.loads(out.read_text(encoding="utf-8"))
    assert first["metadata"]["cache_hit"] is False
    monkeypatch.setenv("GITHUB_SHA", "commit-two")
    experiment.main()
    second = json.loads(out.read_text(encoding="utf-8"))
    assert second["metadata"]["cache_hit"] is True
    assert second["metadata"]["git_commit"] == "commit-two"
    assert second["metadata"]["cache_key"] == first["metadata"]["cache_key"]
    params.write_text(
        json.dumps({"min_votes": 1500, "dataset_version": "test-v2"}), encoding="utf-8"
    )
    experiment.main()
    third = json.loads(out.read_text(encoding="utf-8"))
    assert third["metadata"]["cache_hit"] is False
    assert third["facts"]["eligible"] == 1
    assert third["metadata"]["cache_key"] != first["metadata"]["cache_key"]
    with (tmp_path / "research/anime-metrics.csv").open("a") as stream:
        stream.write("5,Movie,9.0,2000\n")
    experiment.main()
    fourth = json.loads(out.read_text(encoding="utf-8"))
    assert fourth["metadata"]["cache_hit"] is False
    assert fourth["facts"]["eligible"] == 2


def test_chart_uses_current_threshold_in_accessible_text() -> None:
    result = experiment.render_chart(
        {
            "min_votes": 2000,
            "groups": [{"format": "TV", "count": 2}, {"format": "OVA", "count": 1}],
        },
        "__CHART_LABELS__ __CHART_VALUES__ __CHART_SERIES_LABEL__ __CHART_SUMMARY__ __CHART_TABLE_ROWS__",
    )
    assert "2000" in result
    assert "1000" not in result
    assert 'data-raw-value="2"' in result
