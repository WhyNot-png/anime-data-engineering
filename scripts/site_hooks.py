"""Embed the canonical local chart and convert LaTeX to CDN-free MathML."""

import re
from pathlib import Path

from latex2mathml.converter import convert
from mkdocs.utils import get_relative_url

ROOT = Path(__file__).resolve().parents[1]


def on_page_markdown(markdown: str, **kwargs: object) -> str:
    return re.sub(
        r"\$\$\s*(.*?)\s*\$\$",
        lambda match: '<div class="local-math">' + convert(match[1], display="block") + "</div>",
        markdown,
        flags=re.DOTALL,
    )


def on_page_content(html: str, page: object, **kwargs: object) -> str:
    if "<!-- experiment-chart -->" not in html:
        return html
    chart = (ROOT / "docs/generated/chart.html").read_text(encoding="utf-8")
    url = get_relative_url("assets/vendor/chart.umd.js", page.url)
    chart = chart.replace("../assets/vendor/chart.umd.js", url)
    return html.replace("<!-- experiment-chart -->", chart)
