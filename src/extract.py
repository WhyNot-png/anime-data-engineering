from pathlib import Path
import os

from dotenv import load_dotenv
from kaggle.api.kaggle_api_extended import KaggleApi


def extract() -> Path:
    """Download and unzip the Kaggle dataset into data/raw."""
    load_dotenv()
    dataset = os.getenv(
        "KAGGLE_DATASET",
        "sazzadsiddiquelikhon/myanimelist-anime-database-july-2025",
    )
    raw_dir = Path(os.getenv("RAW_DATA_DIR", "data/raw"))
    raw_dir.mkdir(parents=True, exist_ok=True)

    api = KaggleApi()
    api.authenticate()
    api.dataset_download_files(dataset, path=raw_dir, unzip=True)
    return raw_dir
