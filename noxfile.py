"""The same commands locally and in CI; uv.lock remains the dependency authority."""

import nox


@nox.session(venv_backend="none")
def site(session: nox.Session) -> None:
    session.run(
        "uv", "run", "--locked", "--group", "docs", "python", "scripts/experiment.py", external=True
    )
    session.run(
        "uv", "run", "--locked", "--group", "docs", "mkdocs", "build", "--strict", external=True
    )


@nox.session(venv_backend="none")
def benchmark(session: nox.Session) -> None:
    session.run(
        "uv",
        "run",
        "--locked",
        "--group",
        "docs",
        "--group",
        "benchmark",
        "python",
        "scripts/benchmark_ssg.py",
        external=True,
    )
