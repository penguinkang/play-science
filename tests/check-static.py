#!/usr/bin/env python3
"""Verify the static application shell exposes unique UI landmarks."""

from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path


REQUIRED_IDS = (
    "landing-screen",
    "game-screen",
    "world-canvas",
    "formula-inspector",
    "subtitle",
    "subtitle-toggle",
    "step-button",
    "continue-button",
    "fast-episode-button",
    "train-100-button",
    "reset-button",
    "reward-chart",
)


class IdCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.ids.extend(value for name, value in attrs if name == "id" and value)


index_path = Path(__file__).resolve().parents[1] / "index.html"
assert index_path.exists(), f"Missing application shell: {index_path}"

parser = IdCollector()
parser.feed(index_path.read_text(encoding="utf-8"))

for required_id in REQUIRED_IDS:
    count = parser.ids.count(required_id)
    assert count == 1, f"Expected id={required_id!r} exactly once, found {count}"

print(f"PASS: found {len(REQUIRED_IDS)} required landmarks exactly once")
