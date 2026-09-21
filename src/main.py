from pathlib import Path

from src.extract import extract
from src.load import load
from src.transform import transform


def main() -> None:
    raw_dir = extract()
    parquet_path = transform(raw_dir, Path("data/processed"))
    row_count = load(parquet_path)
    print(f"ETL completed: {row_count} rows loaded")


if __name__ == "__main__":
    main()
