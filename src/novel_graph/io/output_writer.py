from __future__ import annotations

import json
from pathlib import Path

from novel_graph.domain.models import LightweightGraph


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_markdown(path: Path, markdown: str) -> None:
    ensure_dir(path.parent)
    path.write_text(markdown, encoding="utf-8")


def write_graph_json(path: Path, graph: LightweightGraph) -> None:
    ensure_dir(path.parent)
    path.write_text(
        json.dumps(graph.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
