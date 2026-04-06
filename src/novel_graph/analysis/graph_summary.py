from __future__ import annotations

from novel_graph.domain.models import LightweightGraph


def _metadata_items(graph: LightweightGraph, key: str) -> list[dict]:
    value = (graph.metadata or {}).get(key)
    return value if isinstance(value, list) else []


def _metadata_list(graph: LightweightGraph, key: str) -> list[str]:
    value = (graph.metadata or {}).get(key)
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def summarize_graph(graph: LightweightGraph) -> str:
    if not graph.nodes:
        return "未抽取到稳定知识图谱，建议缩小到单段正文后重试。"

    protagonist = (graph.metadata or {}).get("protagonist")
    characters = _metadata_items(graph, "character_profiles") or _metadata_items(
        graph, "core_characters"
    )
    locations = _metadata_items(graph, "location_profiles")
    factions = _metadata_items(graph, "faction_profiles")
    plots = _metadata_items(graph, "plot_threads")
    relationships = _metadata_items(graph, "relationship_highlights")
    worldlines = _metadata_list(graph, "worldline_order")

    parts: list[str] = []
    if protagonist:
        parts.append(f"以 {protagonist} 为核心")
    if characters:
        parts.append(
            "人物包括 "
            + "、".join(item["name"] for item in characters[:5] if item.get("name"))
        )
    if locations:
        parts.append(
            "关键地点包括 "
            + "、".join(item["name"] for item in locations[:4] if item.get("name"))
        )
    if factions:
        parts.append(
            "关键势力包括 "
            + "、".join(item["name"] for item in factions[:4] if item.get("name"))
        )
    if plots:
        parts.append(
            "主线剧情覆盖 "
            + "；".join(
                f"{item['title']}({item.get('worldline') or '待复核'})"
                for item in plots[:4]
                if item.get("title")
            )
        )
    if relationships:
        parts.append(
            "高频关系为 "
            + "；".join(
                f"{item['source']}->{item['target']}({item['relation']})"
                for item in relationships[:4]
                if item.get("source") and item.get("target")
            )
        )
    if worldlines:
        parts.append("世界线顺序为 " + " -> ".join(worldlines[:6]))

    if not parts:
        return f"图谱已抽取 {len(graph.nodes)} 个节点、{len(graph.edges)} 条关系。"
    return "；".join(parts) + "。"
