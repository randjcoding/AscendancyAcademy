"""Small HTML helpers for notes and reminder compose."""
from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser


class _Plain(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"p", "div", "li", "br", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")


def html_to_plain(raw: str) -> str:
    parser = _Plain()
    parser.feed(raw or "")
    text = unescape("".join(parser.parts))
    return re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]{2,}", " ", text)).strip()
