"""Content-addressed scientific calculation; no network or credentials required."""

from __future__ import annotations

import csv
import hashlib
import html
import json
import math
import os
import subprocess
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

ROOT = Path(__file__).resolve().parents[1]


class Group(TypedDict):
    format: str
    count: int
    mean_score: float


def calculate(data: Path, parameters: dict[str, Any]) -> dict[str, Any]:
    groups: dict[str, list[float]] = defaultdict(list)
    ids: set[str] = set()
    missing_score = 0
    total = 0
    with data.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            total += 1
            if row["mal_id"] in ids:
                raise ValueError(f"Duplicate mal_id: {row['mal_id']}")
            ids.add(row["mal_id"])
            if not row["score"] or not row["scored_by"]:
                missing_score += 1
                continue
            score, votes = float(row["score"]), float(row["scored_by"])
            if not math.isfinite(score) or not 0 <= score <= 10 or votes < 0:
                raise ValueError("Invalid score or vote count")
            if votes >= parameters["min_votes"]:
                groups[row["type"] or "Unknown"].append(score)
    rows: list[Group] = [
        {"format": name, "count": len(values), "mean_score": sum(values) / len(values)}
        for name, values in groups.items()
    ]
    rows.sort(key=lambda row: (-row["count"], row["format"]))
    return {
        "min_votes": parameters["min_votes"],
        "source_rows": total,
        "missing_scores": missing_score,
        "eligible": sum(row["count"] for row in rows),
        "groups": rows,
        "comparison_plan": {
            "question": "How are titles with at least the minimum vote count distributed by format?",
            "grain": "one unique MyAnimeList mal_id",
            "population": "July 2025 snapshot, score available, votes >= min_votes",
            "unit": "titles; mean score is a secondary non-additive statistic",
            "chart": "categorical-bars: all formats if <=7, otherwise six + additive remainder",
            "table": "all formats, count and unweighted mean of title-level scores",
            "limitations": "Selection by vote count; not a causal comparison or pooled user rating",
        },
    }


def render_chart(facts: dict[str, Any], template: str) -> str:
    rows = facts["groups"]
    display = (
        rows
        if len(rows) <= 7
        else rows[:6]
        + [{"format": "Remaining formats", "count": sum(r["count"] for r in rows[6:])}]
    )
    labels = [r["format"] for r in display]
    values = [r["count"] for r in display]
    series_label = f"Тайтлов с минимум {facts.get('min_votes', 1000)} голосами"
    summary = "; ".join(f"{r['format']}: {r['count']} titles" for r in display)
    table = "".join(
        f'<tr><td>{html.escape(str(r["format"]))}</td><td data-observation-key="{html.escape(str(r["format"]))}" data-series-key="{series_label}" data-raw-value="{r["count"]}" data-value-kind="count">{r["count"]:,}</td></tr>'
        for r in display
    )
    replacements = {
        "__CHART_SERIES_LABEL__": series_label,
        "__CHART_LIBRARY_URL__": "../assets/vendor/chart.umd.js",
        "__CHART_LABELS__": json.dumps(labels, ensure_ascii=False),
        "__CHART_VALUES__": json.dumps(values),
        "__CHART_SUMMARY__": html.escape(summary, quote=True),
        "__CHART_TABLE_ROWS__": table,
    }
    result = template
    for key, value in replacements.items():
        result = result.replace(key, value)
    return result


def main() -> None:
    started = time.perf_counter()
    params = json.loads((ROOT / "research/parameters.json").read_text(encoding="utf-8"))
    source = ROOT / "research/anime-metrics.csv"
    template_path = ROOT / "scripts/chart-template.html"
    template = template_path.read_text(encoding="utf-8") if template_path.exists() else ""
    key_parts = [
        source.read_bytes(),
        (ROOT / "research/parameters.json").read_bytes(),
        Path(__file__).read_bytes(),
        (ROOT / "uv.lock").read_bytes(),
        template.encode(),
    ]
    digest = hashlib.sha256(b"\0".join(key_parts)).hexdigest()
    cache_dir = ROOT / ".cache/experiments"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{digest}.json"
    hit = cached.exists()
    if hit:
        facts = json.loads(cached.read_text(encoding="utf-8"))
    else:
        facts = calculate(source, params)
        cached.write_text(json.dumps(facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    compute_ms = (time.perf_counter() - started) * 1000
    commit = (
        os.environ.get("GITHUB_SHA")
        or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    )
    metadata = {
        "git_commit": commit,
        "built_at_utc": datetime.now(UTC).isoformat(),
        "dataset_version": params["dataset_version"],
        "min_votes": params["min_votes"],
        "input_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "cache_key": digest,
        "cache_hit": hit,
        "calculation_ms": compute_ms,
    }
    evidence = {"metadata": metadata, "facts": facts}
    out = ROOT / "docs/generated"
    out.mkdir(parents=True, exist_ok=True)
    (out / "evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with (out / "summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["format", "count", "mean_score"])
        writer.writeheader()
        writer.writerows(facts["groups"])
    if template:
        (out / "chart.html").write_text(render_chart(facts, template), encoding="utf-8")
    rows = facts["groups"]
    table = "\n".join(f"| {r['format']} | {r['count']} | {r['mean_score']:.3f} |" for r in rows)
    page = f"""# Результаты эксперимента

Контрольная строка: **ANIME-RESEARCH-LAB3**.

## Что измеряется

Снимок MyAnimeList за июль 2025 года; единица наблюдения — уникальный `mal_id`.
В числовом срезе **{facts["source_rows"]}** тайтлов; у **{facts["missing_scores"]}**
отсутствует оценка. В анализ включены **{facts["eligible"]}** тайтлов с опубликованной
оценкой и минимум **{params["min_votes"]}** голосов. Пропуски не заменяются нулём.
График показывает количество тайтлов по формату, а не количество голосовавших людей.

<!-- experiment-chart -->

## Все форматы

| Формат | Тайтлов в анализе | Средняя оценка тайтла, из 10 |
| --- | ---: | ---: |
{table}

Среднее невзвешенное: каждый тайтл учитывается один раз. Это не средняя оценка
по всем голосам пользователей и не доказательство влияния формата на качество.

<a id="mean-score"></a>
$$
\\bar{{s}} = \\frac{{1}}{{n}}\\sum_{{i=1}}^{{n}}s_i
$$

Формула (1): средняя оценка тайтлов; [ссылка на формулу](#mean-score).
LaTeX преобразуется при сборке в нативный MathML — внешние CDN не нужны.

## Версия публикации

| Метка | Значение |
| --- | --- |
| Коммит кода | `{commit}` |
| Сборка, UTC | `{metadata["built_at_utc"]}` |
| Версия набора данных | `{metadata["dataset_version"]}` |
| SHA-256 входного CSV | `{metadata["input_sha256"]}` |
| Ключ кэша | `{digest}` |
| Результат кэширования | `{"HIT" if hit else "MISS"}` |
| Чтение кэша / расчёт, мс | {compute_ms:.3f} |

[Скачать агрегаты CSV](generated/summary.csv) · [Проверяемые метаданные JSON](generated/evidence.json)

Источник и очистка описаны в [P3](p3.md); ограничения и методика — в [отчёте](report.md).
"""
    (ROOT / "docs/results.md").write_text(page, encoding="utf-8")
    print(json.dumps({"cache_hit": hit, "eligible": facts["eligible"], "ms": compute_ms}))


if __name__ == "__main__":
    main()
