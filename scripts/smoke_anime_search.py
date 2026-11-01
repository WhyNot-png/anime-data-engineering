"""Four hand-picked end-to-end checks, not a benchmark of general accuracy."""

import argparse
from pathlib import Path

from research_graph.embedding import SentenceEncoder
from research_graph.semantic_search import read_index_info, search_index

CASES = (
    ("1535", "Школьник находит тетрадь, которая убивает человека, если вписать его имя."),
    (
        "20",
        "Мальчик хочет стать главным ниндзя своей деревни, а внутри него запечатан девятихвостый лис.",
    ),
    (
        "21",
        "Команда пиратов с капитаном, чьё тело растягивается как резина, ищет великое сокровище.",
    ),
    (
        "199",
        "Девочка работает в бане для духов и пытается спасти родителей, превратившихся в свиней.",
    ),
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    args = parser.parse_args()
    read_index_info(args.index)
    encoder = SentenceEncoder()
    success = True
    for expected, query in CASES:
        hits = search_index(args.index, query, encoder, top_k=5)
        rank = next((i for i, hit in enumerate(hits, start=1) if hit.anime.id == expected), None)
        success = success and rank is not None
        print(f"expected_id={expected}; rank_in_top5={rank}; first={hits[0].anime.title}")
    print("These four queries are smoke checks, not a representative accuracy measurement.")
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
