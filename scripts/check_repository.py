"""Check tracked artifacts, not untracked local working files."""

import subprocess
from pathlib import PurePosixPath


def main() -> int:
    output = subprocess.run(
        ["git", "ls-files", "-z"], check=True, capture_output=True, text=True
    ).stdout
    paths = [path for path in output.split("\0") if path]
    forbidden = []
    for name in paths:
        path = PurePosixPath(name)
        if (
            ".venv" in path.parts
            or "__pycache__" in path.parts
            or path.name == ".env"
            or path.name.startswith(".coverage")
            or path.name == "kaggle.json"
            or path.suffix == ".pyc"
        ):
            forbidden.append(name)
    if forbidden:
        raise SystemExit("Forbidden tracked files: " + ", ".join(forbidden))
    if "uv.lock" not in paths:
        raise SystemExit("uv.lock must be tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
