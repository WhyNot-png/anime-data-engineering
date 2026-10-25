"""Optional Parquet to SQLite loading preserved from the original project."""

import os
from pathlib import Path


def load(parquet_path: Path) -> int:
    """Load transformed data into the anime table."""
    import pandas as pd
    from dotenv import load_dotenv
    from sqlalchemy import create_engine

    from research_graph.config import get_settings

    load_dotenv()
    processed = get_settings().data_dir / "processed"
    processed.mkdir(parents=True, exist_ok=True)
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{processed / 'anime.db'}")
    frame = pd.read_parquet(parquet_path)
    engine = create_engine(database_url)
    try:
        frame.to_sql("anime", engine, if_exists="replace", index=False, chunksize=1000)
    finally:
        engine.dispose()
    return len(frame)
