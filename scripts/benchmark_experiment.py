"""Measure real cache hits/misses and a controlled edit to a copy of source data."""

import csv
import hashlib
import io
import json
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run() -> dict[str, float | bool | int]:
    started = time.perf_counter()
    result = subprocess.run(
        [sys.executable, "scripts/experiment.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    metrics: dict[str, float | bool | int] = json.loads(result.stdout)
    metrics["wall_ms"] = (time.perf_counter() - started) * 1000
    return metrics


def main() -> None:
    data = ROOT / "research/anime-metrics.csv"
    params = ROOT / "research/parameters.json"
    original, parameters = data.read_bytes(), params.read_bytes()
    cold, warm = [], []
    try:
        for _ in range(5):
            shutil.rmtree(ROOT / ".cache/experiments", ignore_errors=True)
            cold.append(run())
            warm.append(run())
        before = json.loads((ROOT / "docs/generated/evidence.json").read_text())
        rows = list(csv.DictReader(io.StringIO(original.decode())))
        changed = [row for row in rows if row["mal_id"] != "1"]
        assert len(changed) == len(rows) - 1
        with data.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["mal_id", "type", "score", "scored_by"])
            writer.writeheader()
            writer.writerows(changed)
        settings = json.loads(parameters)
        settings["dataset_version"] = "controlled-demo-without-mal-id-1"
        params.write_text(json.dumps(settings) + "\n")
        modified = run()
        after = json.loads((ROOT / "docs/generated/evidence.json").read_text())
        assert before["facts"]["eligible"] == after["facts"]["eligible"] + 1
        assert modified["cache_hit"] is False
        metrics = {
            "method": "5 pairs; fresh process per run; cold removes calculation cache; warm reuses exact content key; times measured locally, not claimed as CI or deployment duration",
            "cold_samples": cold,
            "warm_samples": warm,
            "cold_compute_median_ms": statistics.median(float(x["ms"]) for x in cold),
            "warm_compute_median_ms": statistics.median(float(x["ms"]) for x in warm),
            "cold_wall_median_ms": statistics.median(float(x["wall_ms"]) for x in cold),
            "warm_wall_median_ms": statistics.median(float(x["wall_ms"]) for x in warm),
            "controlled_edit": {
                "description": "Remove the real record mal_id=1 from a temporary snapshot; restore original after test; no new fabricated observations",
                "before_input_sha256": hashlib.sha256(original).hexdigest(),
                "after_input_sha256": after["metadata"]["input_sha256"],
                "eligible_before": before["facts"]["eligible"],
                "eligible_after": after["facts"]["eligible"],
                "tv_before": next(
                    x["count"] for x in before["facts"]["groups"] if x["format"] == "TV"
                ),
                "tv_after": next(
                    x["count"] for x in after["facts"]["groups"] if x["format"] == "TV"
                ),
                "cache_hit_after_edit": modified["cache_hit"],
            },
        }
        out = ROOT / "docs/evidence/p3-benchmark.json"
        out.write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n")
        print(
            json.dumps(
                {
                    k: v
                    for k, v in metrics.items()
                    if k.endswith("median_ms") or k == "controlled_edit"
                }
            ),
            flush=True,
        )
    finally:
        data.write_bytes(original)
        params.write_bytes(parameters)
        run()


if __name__ == "__main__":
    main()
