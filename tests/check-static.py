#!/usr/bin/env python3
"""Verify the static application shell exposes unique UI landmarks."""

from __future__ import annotations

import re
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
        self.attributes_by_id: dict[str, dict[str, str | None]] = {}

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attributes = dict(attrs)
        element_id = attributes.get("id")
        if element_id:
            self.ids.append(element_id)
            self.attributes_by_id[element_id] = attributes


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


root = Path(__file__).resolve().parents[1]
index_path = root / "index.html"
require(index_path.exists(), f"Missing application shell: {index_path}")

parser = IdCollector()
index_source = index_path.read_text(encoding="utf-8")
parser.feed(index_source)

for required_id in REQUIRED_IDS:
    count = parser.ids.count(required_id)
    require(count == 1, f"Expected id={required_id!r} exactly once, found {count}")

require(
    parser.attributes_by_id.get("game-title", {}).get("tabindex") == "-1",
    "Expected #game-title to be programmatically focusable with tabindex=-1",
)
readme_source = (root / "README.md").read_text(encoding="utf-8")
for name, source in (("UI", index_source), ("README", readme_source)):
    require("any non-modifier key" not in source.lower(), f"{name} has inaccurate continuation copy")
    require("character key" in source.lower(), f"{name} names character-key continuation")
require(
    "pushes to `main`" in readme_source
    and "github pages workflow" in readme_source.lower(),
    "README must describe the GitHub Pages workflow trigger",
)

workflow_path = root / ".github" / "workflows" / "deploy-pages.yml"
require(workflow_path.exists(), f"Missing GitHub Pages workflow: {workflow_path}")
workflow_source = workflow_path.read_text(encoding="utf-8")

for action in (
    "actions/checkout",
    "actions/configure-pages",
    "actions/upload-pages-artifact",
    "actions/deploy-pages",
):
    require(
        re.search(rf"uses:\s*{re.escape(action)}@v\d+", workflow_source) is not None,
        f"Pages workflow must use an explicit major version of {action}",
    )

for permission in ("pages", "id-token"):
    require(
        re.search(rf"^\s*{permission}:\s*write\s*$", workflow_source, re.MULTILINE)
        is not None,
        f"Pages workflow must grant {permission}: write",
    )

require(
    re.search(
        r"^on:\s*$.*?^\s+push:\s*$.*?^\s+branches:\s*(?:\[\s*main\s*\]|\n\s+-\s*main\s*)$",
        workflow_source,
        re.MULTILINE | re.DOTALL,
    )
    is not None,
    "Pages workflow must run on pushes to main",
)
require(
    re.search(r"^\s*environment:\s*$", workflow_source, re.MULTILINE) is not None
    and re.search(r"^\s*name:\s*github-pages\s*$", workflow_source, re.MULTILINE)
    is not None,
    "Pages deployment must use the github-pages environment",
)
require(
    re.search(r"^concurrency:\s*$", workflow_source, re.MULTILINE) is not None
    and re.search(r"^\s+group:\s*pages\s*$", workflow_source, re.MULTILINE)
    is not None
    and re.search(
        r"^\s+cancel-in-progress:\s*false\s*$", workflow_source, re.MULTILINE
    )
    is not None,
    "Pages workflow must define explicit pages concurrency",
)
require(
    re.search(r"^\s+path:\s*['\"]?\.['\"]?\s*$", workflow_source, re.MULTILINE)
    is not None,
    "Pages artifact must upload the repository root",
)
require(
    re.search(
        r"^\s+include-hidden-files:\s*false\s*$", workflow_source, re.MULTILINE
    )
    is not None,
    "Pages artifact must exclude hidden metadata",
)

print(
    f"PASS: found {len(REQUIRED_IDS)} required landmarks exactly once "
    "and a valid Pages workflow"
)
