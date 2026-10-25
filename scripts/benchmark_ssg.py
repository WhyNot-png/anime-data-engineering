"""Rebuildable microbenchmark, not an end-to-end scientific-feature comparison."""

import importlib.metadata
import json
import platform
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / ".cache/ssg-benchmark"


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def timed(command: list[str], cwd: Path, label: str) -> float:
    start = time.perf_counter()
    result = subprocess.run(command, cwd=cwd, text=True, capture_output=True)
    if result.returncode:
        log = ROOT / ".cache" / f"benchmark-error-{label}.txt"
        log.write_text(result.stdout + result.stderr, encoding="utf-8")
        raise RuntimeError(f"{label} failed; inspect {log}")
    return time.perf_counter() - start


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    common = (
        "Исследование результатов эксперимента: регрессионный анализ и воспроизводимость. "
        "Каждый результат связан с версией исходного кода и данных.\n\n"
    ) * 20 + "| Формат | Тайтлов |\n| --- | --- |\n| TV | 20 |\n\n```python\nx = 1 + 2\n```\n"
    specs = []
    for kind in ["mkdocs", "sphinx", "pelican", "nikola"]:
        home = BASE / kind
        if home.exists():
            shutil.rmtree(home)
        home.mkdir()
        if kind == "nikola":
            subprocess.run(
                [sys.executable, "-m", "nikola", "init", "-q", str(home)],
                check=True,
                capture_output=True,
            )
        for i in range(12):
            name = f"page{i:02d}"
            if kind == "mkdocs":
                write(home / f"docs/{name}.md", f"# Страница {i}\n\n{common}")
            elif kind == "sphinx":
                write(home / f"source/{name}.md", f"# Страница {i}\n\n{common}")
            elif kind == "pelican":
                write(
                    home / f"content/pages/{name}.md",
                    f"Title: Страница {i}\nSlug: {name}\n\n{common}",
                )
            else:
                write(
                    home / f"pages/{name}.md",
                    f"<!--\n.. title: Страница {i}\n.. slug: {name}\n.. date: 2025-07-16 00:00:00 UTC\n-->\n\n{common}",
                )
        if kind == "mkdocs":
            write(
                home / "mkdocs.yml",
                "site_name: Benchmark\ntheme:\n  name: material\n  font: false\n",
            )
            command = [sys.executable, "-m", "mkdocs", "build", "--strict"]
            output, page, mutable = (
                home / "site",
                home / "site/page00/index.html",
                home / "docs/page00.md",
            )
            caches = [home / "site"]
        elif kind == "sphinx":
            write(
                home / "source/conf.py",
                "project='Benchmark'\nextensions=['myst_parser']\nlanguage='ru'\nhtml_theme='alabaster'\n",
            )
            write(
                home / "source/index.md",
                "# Benchmark\n\n```{toctree}\n"
                + "\n".join(f"page{i:02d}" for i in range(12))
                + "\n```\n",
            )
            command = [sys.executable, "-m", "sphinx", "-b", "html", "-W", "source", "output"]
            output, page, mutable = (
                home / "output",
                home / "output/page00.html",
                home / "source/page00.md",
            )
            caches = [home / "output"]
        elif kind == "pelican":
            write(
                home / "pelicanconf.py",
                "AUTHOR='Research'\nSITENAME='Benchmark'\nSITEURL='https://example.org'\nPATH='content'\nTIMEZONE='UTC'\nDEFAULT_LANG='ru'\nCACHE_CONTENT=True\nLOAD_CONTENT_CACHE=True\nFEED_ALL_ATOM=None\nCATEGORY_FEED_ATOM=None\n",
            )
            command = [
                sys.executable,
                "-m",
                "pelican",
                "content",
                "-s",
                "pelicanconf.py",
                "-o",
                "output",
            ]
            output, page, mutable = (
                home / "output",
                home / "output/pages/page00.html",
                home / "content/pages/page00.md",
            )
            caches = [home / "output", home / "cache"]
        else:
            with (home / "conf.py").open("a") as stream:
                stream.write(
                    "\nDEFAULT_LANG='ru'\nTRANSLATIONS={'ru':''}\nBLOG_URL='https://example.org/'\nUSE_CDN=False\nPOSTS=[]\nPAGES=[('pages/*.md','pages','page.tmpl')]\nCOMPILERS={'markdown':['.md']}\n"
                )
            command = [sys.executable, "-m", "nikola", "build"]
            output, page, mutable = (
                home / "output",
                home / "output/pages/page00/index.html",
                home / "pages/page00.md",
            )
            caches = [home / "output", home / "cache", *home.glob(".doit.db*")]
        cold = []
        for _repeat in range(3):
            for path in caches:
                if path.is_dir():
                    shutil.rmtree(path)
                elif path.exists():
                    path.unlink()
            if kind == "nikola":
                for path in home.glob(".doit.db*"):
                    if path.is_file():
                        path.unlink()
            cold.append(timed(command, home, kind))
        incremental = []
        for repeat in range(3):
            with mutable.open("a") as stream:
                stream.write(f"\nIncremental edit {repeat}.\n")
            incremental.append(timed(command, home, kind))
        deploy_files = [p for p in output.rglob("*") if p.is_file() and ".doctrees" not in p.parts]
        if not page.exists():
            matches = list(output.rglob("*page00*"))
            raise RuntimeError(f"Find generated page for {kind}: {matches}")
        specs.append(
            {
                "generator": kind,
                "cold_seconds": cold,
                "cold_median_seconds": statistics.median(cold),
                "incremental_seconds": incremental,
                "incremental_median_seconds": statistics.median(incremental),
                "page_bytes": page.stat().st_size,
                "site_bytes": sum(p.stat().st_size for p in deploy_files),
                "file_count": len(deploy_files),
            }
        )
        print(json.dumps(specs[-1]), flush=True)
    evidence = {
        "environment": {"python": platform.python_version(), "platform": platform.platform()},
        "method": "12 equivalent text pages; 3 clean-output builds and 3 single-page edits; median; no dependency installation/network in timed interval; OS caches not flushed; default themes differ; Sphinx doctrees excluded from deployment size",
        "versions": {
            p: importlib.metadata.version(p)
            for p in ["mkdocs", "mkdocs-material", "Sphinx", "myst-parser", "pelican", "Nikola"]
        },
        "results": specs,
    }
    destination = ROOT / "docs/evidence/ssg-benchmark.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
