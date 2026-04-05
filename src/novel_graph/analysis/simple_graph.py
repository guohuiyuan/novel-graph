from __future__ import annotations

from collections import Counter, defaultdict
import re

from novel_graph.analysis.keywords import top_candidate_names
from novel_graph.domain.models import GraphEdge, GraphNode, LightweightGraph


def _paragraphs(text: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]


def build_lightweight_graph(text: str, max_nodes: int = 14) -> LightweightGraph:
    names = top_candidate_names(text, limit=max_nodes)
    if not names:
        return LightweightGraph()

    paragraph_list = _paragraphs(text)
    node_hits = Counter()
    pair_hits: dict[tuple[str, str], int] = defaultdict(int)

    for paragraph in paragraph_list:
        present = [name for name in names if name in paragraph]
        for name in present:
            node_hits[name] += 1
        for i, left in enumerate(present):
            for right in present[i + 1 :]:
                key = tuple(sorted((left, right)))
                pair_hits[key] += 1

    nodes = [
        GraphNode(
            id=f"n{i+1}", label=name, category="角色", weight=max(node_hits[name], 1)
        )
        for i, name in enumerate(names)
    ]
    id_map = {node.label: node.id for node in nodes}

    edges = [
        GraphEdge(
            source=id_map[a], target=id_map[b], relation="同场互动", weight=weight
        )
        for (a, b), weight in sorted(
            pair_hits.items(), key=lambda item: item[1], reverse=True
        )
        if weight >= 2
    ]

    return LightweightGraph(nodes=nodes, edges=edges)


def summarize_graph(graph: LightweightGraph) -> str:
    if not graph.nodes:
        return "未抽取到稳定角色实体，建议补充更多正文内容后重试。"

    core_nodes = sorted(graph.nodes, key=lambda node: node.weight, reverse=True)[:5]
    core_text = "、".join(f"{node.label}(出现{node.weight}次)" for node in core_nodes)

    if not graph.edges:
        return f"核心角色：{core_text}。角色共现关系较弱，暂未形成稳定互动边。"

    core_edges = sorted(graph.edges, key=lambda edge: edge.weight, reverse=True)[:5]
    edge_text = "；".join(
        f"{edge.source}->{edge.target}(共现{edge.weight}次)" for edge in core_edges
    )
    return f"核心角色：{core_text}。高频互动边：{edge_text}。"
