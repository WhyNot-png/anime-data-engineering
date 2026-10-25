"""Verify local publication artifacts without a browser or external services."""

import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class Assets(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        if tag in {"script", "img", "iframe"} and data.get("src"):
            self.urls.append(str(data["src"]))
        if tag == "link" and data.get("rel") == "stylesheet" and data.get("href"):
            self.urls.append(str(data["href"]))


def main() -> None:
    root = Path("site").resolve()
    index = (root / "index.html").read_text(encoding="utf-8")
    results = (root / "results/index.html").read_text(encoding="utf-8")
    assert "ANIME-RESEARCH-LAB3" in index
    assert "<math" in results
    assert "canonicalBars" in results
    search = json.loads((root / "search/search_index.json").read_text(encoding="utf-8"))
    assert len(search["docs"]) > 5
    checked = 0
    for file in root.rglob("*.html"):
        parser = Assets()
        parser.feed(file.read_text(encoding="utf-8"))
        for url in parser.urls:
            parsed = urlsplit(url)
            if parsed.scheme in {"http", "https"} or parsed.netloc:
                raise AssertionError(f"External asset in {file.relative_to(root)}: {url}")
            if parsed.scheme == "data" or not parsed.path:
                continue
            path = unquote(parsed.path)
            asset = (file.parent / path).resolve()
            if path.startswith("/"):
                asset = root / path.removeprefix("/anime-data-engineering/").lstrip("/")
            assert asset.is_relative_to(root), (file, url)
            assert asset.is_file(), (file, url)
            checked += 1
    print(
        json.dumps(
            {
                "html_files": len(list(root.rglob("*.html"))),
                "asset_references": checked,
                "external_assets": 0,
                "mathml": True,
                "search_entries": len(search["docs"]),
            }
        )
    )


if __name__ == "__main__":
    main()
