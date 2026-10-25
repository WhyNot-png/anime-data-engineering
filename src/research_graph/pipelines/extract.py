"""Optional Kaggle extraction; importing the core package needs no credentials."""

import os
from pathlib import Path


def extract() -> Path:
    """Download the original dataset using the separate Kaggle credentials."""
    from dotenv import load_dotenv
    from kaggle.api.kaggle_api_extended import KaggleApi

    from research_graph.config import get_settings

    load_dotenv()
    dataset = os.getenv(
        "KAGGLE_DATASET", "sazzadsiddiquelikhon/myanimelist-anime-database-july-2025"
    )
    raw_dir = Path(os.getenv("RAW_DATA_DIR", str(get_settings().data_dir / "raw")))
    raw_dir.mkdir(parents=True, exist_ok=True)
    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(dataset, path=raw_dir, unzip=True)
    return raw_dir
