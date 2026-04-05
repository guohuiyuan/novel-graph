from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class ScanMode(str, Enum):
    DIRECT = "direct"
    GRAPH = "graph"
    BOTH = "both"


class Provider(str, Enum):
    HEURISTIC = "heuristic"
    OPENAI = "openai"


@dataclass(slots=True)
class NovelInput:
    source_path: Path
    title: str
    raw_text: str


@dataclass(slots=True)
class GraphNode:
    id: str
    label: str
    category: str
    weight: int = 1


@dataclass(slots=True)
class GraphEdge:
    source: str
    target: str
    relation: str
    weight: int = 1


@dataclass(slots=True)
class LightweightGraph:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nodes": [asdict(node) for node in self.nodes],
            "edges": [asdict(edge) for edge in self.edges],
        }


@dataclass(slots=True)
class ScanResult:
    title: str
    mode: ScanMode
    markdown: str
    graph: LightweightGraph | None = None
