from pathlib import Path
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine


def load(parquet_path: Path) -> int:
    """Load transformed data into the anime table."""
    load_dotenv()
    database_url = os.getenv(
        "DATABASE_URL", "sqlite:///data/processed/anime.db"
    )
    Path("data/processed").mkdir(parents=True, exist_ok=True)

    frame = pd.read_parquet(parquet_path)
    engine = create_engine(database_url)
    frame.to_sql("anime", engine, if_exists="replace", index=False, chunksize=1000)
    return len(frame)
