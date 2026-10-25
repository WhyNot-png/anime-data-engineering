"""Optional CSV to Parquet transformation preserved from the original project."""

import re
from pathlib import Path


def normalize_column(name: str) -> str:
    """Convert a column name to lowercase snake_case."""
    return re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower()).strip("_")


def transform(raw_dir: Path, output_dir: Path | None = None) -> Path:
    """Read the largest CSV, normalize it and save deduplicated rows as Parquet."""
    csv_files = list(raw_dir.rglob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"CSV files were not found in {raw_dir}")

    import pandas as pd

    from research_graph.config import get_settings

    source = max(csv_files, key=lambda path: path.stat().st_size)
    frame = pd.read_csv(source, low_memory=False)
    frame.columns = [normalize_column(column) for column in frame.columns]
    frame = frame.drop_duplicates().reset_index(drop=True)
    output_dir = output_dir or get_settings().data_dir / "processed"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / "anime_clean.parquet"
    frame.to_parquet(output, index=False)
    return output
