from pathlib import Path
import re

import pandas as pd


def normalize_column(name: str) -> str:
    """Convert a column name to lowercase snake_case."""
    value = re.sub(r"[^a-zA-Z0-9]+", "_", str(name).strip().lower())
    return value.strip("_")


def transform(raw_dir: Path, output_dir: Path | None = None) -> Path:
    """Read the largest CSV, normalize it, and save it as Parquet."""
    csv_files = list(raw_dir.rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"CSV files were not found in {raw_dir}")

    source = max(csv_files, key=lambda path: path.stat().st_size)
    frame = pd.read_csv(source, low_memory=False)
    frame.columns = [normalize_column(column) for column in frame.columns]
    frame = frame.drop_duplicates().reset_index(drop=True)

    output_dir = output_dir or Path("data/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "anime_clean.parquet"
    frame.to_parquet(output, index=False)
    return output
