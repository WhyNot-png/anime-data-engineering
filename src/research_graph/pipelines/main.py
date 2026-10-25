"""Run the original ETL only when explicitly requested."""

import logging
import os
from pathlib import Path

from research_graph.config import get_settings
from research_graph.logging_setup import setup_logging
from research_graph.pipelines.extract import extract
from research_graph.pipelines.load import load
from research_graph.pipelines.transform import transform


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level, settings.log_format)
    raw_dir = extract()
    output = Path(os.getenv("PROCESSED_DATA_DIR", str(settings.data_dir / "processed")))
    parquet_path = transform(raw_dir, output)
    row_count = load(parquet_path)
    logging.getLogger(__name__).info("ETL completed: %d rows loaded", row_count)


if __name__ == "__main__":  # pragma: no cover
    main()
