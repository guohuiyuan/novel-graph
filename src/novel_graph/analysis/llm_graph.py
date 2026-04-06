from __future__ import annotations

import json
import re
from typing import Any

from novel_graph.domain.models import GraphEdge, GraphNode, LightweightGraph, NovelInput
from novel_graph.services.llm_client import LLMClient
from novel_graph.services.prompt_repo import read_prompt, read_resource

SYSTEM_PROMPT = (
    "你是小说原文知识图谱构建器。"
    "请严格参考 MiroFish 的前半段思路：先按分段抽取实体与关系，再补齐人物、地点、势力、剧情档案，"
    "最后输出可供后续扫书和原文简明解说复用的结构化 JSON 图谱。"
)

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
_SPLIT_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")
_CHAPTER_HEADING_RE = re.compile(
    r"^(第[0-9零一二三四五六七八九十百千万两]+[章节卷回幕篇]|chapter\s*\d+|#{1,3}\s+)",
    flags=re.IGNORECASE,
)

_ROMANCE_TAG_HINTS = (
    "女主",
    "后宫",
    "暧昧",
    "道侣",
    "恋人",
    "妻",
    "妾",
    "夫人",
    "红颜",
    "伴生",
    "联姻",
    "青梅",
)
_IMPORTANCE_RANK = {"lead": 3, "major": 2, "supporting": 1, "minor": 0}
_DEFAULT_SUMMARIES = {
    "character": "正文证据不足，人物简介待复核。",
    "location": "正文证据不足，地点定位待复核。",
    "faction": "正文证据不足，势力定位待复核。",
    "plot": "正文证据不足，剧情线待复核。",
}
_DEFAULT_EVIDENCE = "正文证据待补"
_WORLDLINE_PLACEHOLDER = "待复核"


def _estimate_tokens(text: str) -> int:
    return len(_SPLIT_TOKEN_RE.findall(text))


def _split_hard(text: str, token_budget: int) -> list[str]:
    if token_budget <= 0:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_tokens = 0
    for line in text.splitlines():
        line_text = line.strip()
        if not line_text:
            continue
        line_tokens = _estimate_tokens(line_text)
        if current and current_tokens + line_tokens > token_budget:
            chunks.append("\n".join(current).strip())
            current = [line_text]
            current_tokens = line_tokens
            continue
        if line_tokens > token_budget:
            sentence_parts = [
                part.strip()
                for part in re.split(r"(?<=[。！？!?；;])", line_text)
                if part.strip()
            ]
            if len(sentence_parts) > 1:
                if current:
                    chunks.append("\n".join(current).strip())
                    current = []
                    current_tokens = 0
                buffer: list[str] = []
                buffer_tokens = 0
                for part in sentence_parts:
                    part_tokens = _estimate_tokens(part)
                    if buffer and buffer_tokens + part_tokens > token_budget:
                        chunks.append("".join(buffer).strip())
                        buffer = [part]
                        buffer_tokens = part_tokens
                    else:
                        buffer.append(part)
                        buffer_tokens += part_tokens
                if buffer:
                    chunks.append("".join(buffer).strip())
                continue

        current.append(line_text)
        current_tokens += line_tokens

    if current:
        chunks.append("\n".join(current).strip())
    return [chunk for chunk in chunks if chunk]


def _split_block(block: str, token_budget: int) -> list[str]:
    if _estimate_tokens(block) <= token_budget:
        return [block]

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", block) if part.strip()]
    if len(paragraphs) > 1:
        pieces: list[str] = []
        for paragraph in paragraphs:
            pieces.extend(_split_block(paragraph, token_budget))
        return pieces

    return _split_hard(block, token_budget)


def _chapter_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    current: list[str] = []

    for line in lines:
        is_heading = bool(_CHAPTER_HEADING_RE.match(line.strip()))
        if is_heading and current:
            block = "\n".join(current).strip()
            if block:
                blocks.append(block)
            current = [line]
            continue
        current.append(line)

    if current:
        block = "\n".join(current).strip()
        if block:
            blocks.append(block)

    if blocks:
        return blocks

    loose_blocks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    return loose_blocks or [text]


def _split_text_for_llm(text: str, token_budget: int) -> list[str]:
    if token_budget <= 0 or _estimate_tokens(text) <= token_budget:
        return [text]

    blocks = _chapter_blocks(text)
    segments: list[str] = []
    current_blocks: list[str] = []
    current_tokens = 0

    for block in blocks:
        block_parts = _split_block(block, token_budget)
        for part in block_parts:
            part_tokens = _estimate_tokens(part)
            if current_blocks and current_tokens + part_tokens > token_budget:
                segments.append("\n\n".join(current_blocks).strip())
                current_blocks = [part]
                current_tokens = part_tokens
            else:
                current_blocks.append(part)
                current_tokens += part_tokens

    if current_blocks:
        segments.append("\n\n".join(current_blocks).strip())

    return [segment for segment in segments if segment]


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _coerce_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "是"}:
        return True
    if text in {"false", "0", "no", "n", "否"}:
        return False
    return default


def _coerce_str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _coerce_int_list(value: Any) -> list[int]:
    if not isinstance(value, list):
        return []
    result: list[int] = []
    for item in value:
        try:
            result.append(int(item))
        except (TypeError, ValueError):
            continue
    return sorted(set(result))


def _merge_unique(items: list[str]) -> list[str]:
    merged: list[str] = []
    for item in items:
        if item and item not in merged:
            merged.append(item)
    return merged


def _importance_value(value: str) -> int:
    return _IMPORTANCE_RANK.get(value, 0)


def _normalize_entity_profile(
    item: dict[str, Any],
    *,
    default_entity_type: str,
    fallback_role: str,
) -> dict[str, Any]:
    entity_type = _coerce_str(item.get("entity_type"), default_entity_type).lower()
    return {
        "name": _coerce_str(item.get("name")),
        "entity_type": entity_type,
        "role": _coerce_str(item.get("role"), fallback_role),
        "worldline": _coerce_str(item.get("worldline"), _WORLDLINE_PLACEHOLDER),
        "chapter_hits": _coerce_int(item.get("chapter_hits"), 0),
        "score": _coerce_int(item.get("score"), 10),
        "summary": _coerce_str(
            item.get("summary"),
            _DEFAULT_SUMMARIES.get(entity_type, _DEFAULT_SUMMARIES["character"]),
        ),
        "tags": _merge_unique(_coerce_str_list(item.get("tags"))),
        "risk_tags": _merge_unique(_coerce_str_list(item.get("risk_tags"))),
        "aliases": _merge_unique(_coerce_str_list(item.get("aliases"))),
        "segment_indexes": _coerce_int_list(item.get("segment_indexes")),
        "evidence": _coerce_str(item.get("evidence"), _DEFAULT_EVIDENCE),
        "relation_summary": _coerce_str(item.get("relation_summary")),
        "gender": _coerce_str(item.get("gender"), "unknown").lower(),
        "importance": _coerce_str(item.get("importance"), "supporting").lower(),
        "is_protagonist": _coerce_bool(item.get("is_protagonist")),
        "is_romance_interest": _coerce_bool(item.get("is_romance_interest")),
    }


def _profile_sort_key(profile: dict[str, Any]) -> tuple[int, int, int, int, int]:
    return (
        int(profile.get("is_protagonist", False)),
        _importance_value(str(profile.get("importance", "supporting"))),
        _coerce_int(profile.get("score"), 0),
        _coerce_int(profile.get("chapter_hits"), 0),
        len(_coerce_str(profile.get("name"))),
    )


def _merge_entity_profiles(
    items: list[dict[str, Any]],
    *,
    default_entity_type: str,
    fallback_role: str,
) -> list[dict]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for raw in items:
        profile = _normalize_entity_profile(
            raw,
            default_entity_type=default_entity_type,
            fallback_role=fallback_role,
        )
        if not profile["name"]:
            continue

        key = (profile["entity_type"], profile["name"])
        if key not in merged:
            merged[key] = profile
            continue

        existing = merged[key]
        existing["chapter_hits"] += profile["chapter_hits"]
        existing["score"] = max(existing["score"], profile["score"])
        if existing["role"] == fallback_role and profile["role"] != fallback_role:
            existing["role"] = profile["role"]
        if (
            existing["worldline"] == _WORLDLINE_PLACEHOLDER
            and profile["worldline"] != _WORLDLINE_PLACEHOLDER
        ):
            existing["worldline"] = profile["worldline"]
        if existing["summary"] == _DEFAULT_SUMMARIES.get(
            profile["entity_type"], _DEFAULT_SUMMARIES["character"]
        ) and profile["summary"]:
            existing["summary"] = profile["summary"]
        existing["tags"] = _merge_unique(existing["tags"] + profile["tags"])
        existing["risk_tags"] = _merge_unique(existing["risk_tags"] + profile["risk_tags"])
        existing["aliases"] = _merge_unique(existing["aliases"] + profile["aliases"])
        existing["segment_indexes"] = sorted(
            set(existing["segment_indexes"] + profile["segment_indexes"])
        )
        if existing["evidence"] == _DEFAULT_EVIDENCE and profile["evidence"]:
            existing["evidence"] = profile["evidence"]
        if not existing["relation_summary"] and profile["relation_summary"]:
            existing["relation_summary"] = profile["relation_summary"]
        if existing["gender"] == "unknown" and profile["gender"] != "unknown":
            existing["gender"] = profile["gender"]
        if _importance_value(profile["importance"]) > _importance_value(existing["importance"]):
            existing["importance"] = profile["importance"]
        existing["is_protagonist"] = existing["is_protagonist"] or profile["is_protagonist"]
        existing["is_romance_interest"] = (
            existing["is_romance_interest"] or profile["is_romance_interest"]
        )

    return sorted(merged.values(), key=_profile_sort_key, reverse=True)


def _normalize_relationship(item: dict[str, Any]) -> dict[str, Any] | None:
    source = _coerce_str(item.get("source"))
    target = _coerce_str(item.get("target"))
    if not source or not target or source == target:
        return None

    return {
        "source": source,
        "target": target,
        "relation": _coerce_str(item.get("relation"), "关联"),
        "chapter_hits": _coerce_int(item.get("chapter_hits"), 0),
        "weight": max(
            _coerce_int(item.get("weight"), 0),
            _coerce_int(item.get("chapter_hits"), 1),
            1,
        ),
        "evidence": _coerce_str(item.get("evidence"), _DEFAULT_EVIDENCE),
        "tags": _merge_unique(_coerce_str_list(item.get("tags"))),
        "segment_indexes": _coerce_int_list(item.get("segment_indexes")),
    }


def _merge_relationships(items: list[dict[str, Any]]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}

    for raw in items:
        relation = _normalize_relationship(raw)
        if relation is None:
            continue

        key = (relation["source"], relation["target"], relation["relation"])
        if key not in merged:
            merged[key] = relation
            continue

        existing = merged[key]
        existing["chapter_hits"] += relation["chapter_hits"]
        existing["weight"] += relation["weight"]
        existing["tags"] = _merge_unique(existing["tags"] + relation["tags"])
        existing["segment_indexes"] = sorted(
            set(existing["segment_indexes"] + relation["segment_indexes"])
        )
        if existing["evidence"] == _DEFAULT_EVIDENCE and relation["evidence"]:
            existing["evidence"] = relation["evidence"]

    return sorted(
        merged.values(),
        key=lambda item: (item["weight"], item["chapter_hits"], len(item["tags"])),
        reverse=True,
    )


def _normalize_plot_thread(item: dict[str, Any]) -> dict[str, Any] | None:
    title = _coerce_str(item.get("title"))
    if not title:
        return None

    return {
        "title": title,
        "worldline": _coerce_str(item.get("worldline"), _WORLDLINE_PLACEHOLDER),
        "stage": _coerce_str(item.get("stage"), "待复核"),
        "summary": _coerce_str(item.get("summary"), _DEFAULT_SUMMARIES["plot"]),
        "importance": _coerce_int(item.get("importance"), 10),
        "involved_characters": _merge_unique(_coerce_str_list(item.get("involved_characters"))),
        "key_locations": _merge_unique(_coerce_str_list(item.get("key_locations"))),
        "related_factions": _merge_unique(_coerce_str_list(item.get("related_factions"))),
        "tags": _merge_unique(_coerce_str_list(item.get("tags"))),
        "segment_indexes": _coerce_int_list(item.get("segment_indexes")),
        "evidence": _coerce_str(item.get("evidence"), _DEFAULT_EVIDENCE),
    }


def _merge_plot_threads(items: list[dict[str, Any]]) -> list[dict]:
    merged: dict[tuple[str, str], dict[str, Any]] = {}

    for raw in items:
        plot = _normalize_plot_thread(raw)
        if plot is None:
            continue

        key = (plot["worldline"], plot["title"])
        if key not in merged:
            merged[key] = plot
            continue

        existing = merged[key]
        existing["importance"] = max(existing["importance"], plot["importance"])
        if existing["stage"] == "待复核" and plot["stage"] != "待复核":
            existing["stage"] = plot["stage"]
        if existing["summary"] == _DEFAULT_SUMMARIES["plot"] and plot["summary"]:
            existing["summary"] = plot["summary"]
        existing["involved_characters"] = _merge_unique(
            existing["involved_characters"] + plot["involved_characters"]
        )
        existing["key_locations"] = _merge_unique(existing["key_locations"] + plot["key_locations"])
        existing["related_factions"] = _merge_unique(
            existing["related_factions"] + plot["related_factions"]
        )
        existing["tags"] = _merge_unique(existing["tags"] + plot["tags"])
        existing["segment_indexes"] = sorted(
            set(existing["segment_indexes"] + plot["segment_indexes"])
        )
        if existing["evidence"] == _DEFAULT_EVIDENCE and plot["evidence"]:
            existing["evidence"] = plot["evidence"]

    return sorted(
        merged.values(),
        key=lambda item: (item["importance"], len(item["involved_characters"]), len(item["tags"])),
        reverse=True,
    )


def _compact_segment_overview(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []

    overviews: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        overviews.append(
            {
                "label": _coerce_str(
                    item.get("label") or item.get("worldline"),
                    _WORLDLINE_PLACEHOLDER,
                ),
                "summary": _coerce_str(item.get("summary"), "该阶段摘要待复核。"),
                "heroine_focus": _coerce_str(item.get("heroine_focus")),
                "key_characters": _merge_unique(_coerce_str_list(item.get("key_characters"))),
                "key_locations": _merge_unique(_coerce_str_list(item.get("key_locations"))),
                "key_events": _merge_unique(_coerce_str_list(item.get("key_events"))),
            }
        )
    return overviews


def _merge_worldline_order(*groups: list[str]) -> list[str]:
    merged: list[str] = []
    for items in groups:
        for item in items:
            if item and item not in merged and item != _WORLDLINE_PLACEHOLDER:
                merged.append(item)
    return merged


def _is_romance_profile(profile: dict[str, Any]) -> bool:
    if profile.get("entity_type") != "character" or profile.get("is_protagonist"):
        return False
    if profile.get("is_romance_interest"):
        return True

    haystack = " ".join(
        [
            _coerce_str(profile.get("role")),
            _coerce_str(profile.get("summary")),
            _coerce_str(profile.get("relation_summary")),
            " ".join(_coerce_str_list(profile.get("tags"))),
        ]
    )
    return any(token in haystack for token in _ROMANCE_TAG_HINTS)


def _derive_worldline_order(
    payload: dict[str, Any],
    protagonist_profile: dict[str, Any],
    character_profiles: list[dict],
    location_profiles: list[dict],
    plot_threads: list[dict],
    segment_overview: list[dict],
) -> list[str]:
    return _merge_worldline_order(
        _coerce_str_list(payload.get("worldline_order")),
        [protagonist_profile.get("worldline", _WORLDLINE_PLACEHOLDER)],
        [item.get("label", _WORLDLINE_PLACEHOLDER) for item in segment_overview],
        [item.get("worldline", _WORLDLINE_PLACEHOLDER) for item in plot_threads],
        [item.get("worldline", _WORLDLINE_PLACEHOLDER) for item in character_profiles],
        [item.get("worldline", _WORLDLINE_PLACEHOLDER) for item in location_profiles],
    )


def _derive_segment_overview(
    payload: dict[str, Any],
    *,
    worldline_order: list[str],
    heroine_profiles: list[dict],
    character_profiles: list[dict],
    location_profiles: list[dict],
    plot_threads: list[dict],
) -> list[dict[str, Any]]:
    existing = _compact_segment_overview(payload.get("segment_overview"))
    if existing:
        return existing

    grouped_plots: dict[str, list[dict]] = {}
    for plot in plot_threads:
        grouped_plots.setdefault(plot.get("worldline", _WORLDLINE_PLACEHOLDER), []).append(plot)

    grouped_characters: dict[str, list[dict]] = {}
    for item in character_profiles:
        grouped_characters.setdefault(item.get("worldline", _WORLDLINE_PLACEHOLDER), []).append(item)

    grouped_locations: dict[str, list[dict]] = {}
    for item in location_profiles:
        grouped_locations.setdefault(item.get("worldline", _WORLDLINE_PLACEHOLDER), []).append(item)

    heroine_by_worldline: dict[str, list[str]] = {}
    for item in heroine_profiles:
        heroine_by_worldline.setdefault(item.get("worldline", _WORLDLINE_PLACEHOLDER), []).append(
            item["name"]
        )

    overviews: list[dict[str, Any]] = []
    labels = worldline_order or list(grouped_plots)
    for label in labels:
        plots = grouped_plots.get(label, [])
        characters = grouped_characters.get(label, [])
        locations = grouped_locations.get(label, [])
        if not any((plots, characters, locations)):
            continue

        summary = "；".join(item["summary"] for item in plots[:2] if item.get("summary"))
        if not summary:
            summary = "该阶段以人物扩张和关系推进为主。"
        overviews.append(
            {
                "label": label,
                "summary": summary,
                "heroine_focus": "、".join(heroine_by_worldline.get(label, [])[:3]),
                "key_characters": [item["name"] for item in characters[:5]],
                "key_locations": [item["name"] for item in locations[:4]],
                "key_events": [item["title"] for item in plots[:4]],
            }
        )
    return overviews


def _derive_supporting_profiles(
    payload: dict[str, Any],
    *,
    protagonist_name: str,
    heroine_names: set[str],
    character_profiles: list[dict],
) -> list[dict]:
    explicit = _merge_entity_profiles(
        payload.get("supporting_profiles") or [],
        default_entity_type="character",
        fallback_role="关键人物",
    )
    if explicit:
        return explicit[:12]

    return [
        item
        for item in character_profiles
        if item["name"] != protagonist_name and item["name"] not in heroine_names
    ][:12]


def _derive_core_characters(
    protagonist_profile: dict[str, Any],
    heroine_profiles: list[dict],
    supporting_profiles: list[dict],
    character_profiles: list[dict],
) -> list[dict]:
    ordered: list[dict] = []
    seen: set[str] = set()
    for item in [protagonist_profile, *heroine_profiles, *supporting_profiles, *character_profiles]:
        name = item.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        ordered.append(item)
        if len(ordered) >= 12:
            break
    return ordered


def _append_edge(bucket: dict[tuple[str, str, str], GraphEdge], edge: GraphEdge) -> None:
    key = (edge.source, edge.target, edge.relation)
    if key not in bucket:
        bucket[key] = edge
        return

    existing = bucket[key]
    existing.weight += edge.weight
    existing.chapter_hits += edge.chapter_hits
    existing.tags = _merge_unique(existing.tags + edge.tags)
    if existing.evidence in {None, "", _DEFAULT_EVIDENCE} and edge.evidence:
        existing.evidence = edge.evidence


def _graph_payload(graph: LightweightGraph) -> dict[str, Any]:
    metadata = graph.metadata or {}
    return {
        "protagonist": metadata.get("protagonist"),
        "heroine_pool_estimate": metadata.get("heroine_pool_estimate", 0),
        "chunk_count": metadata.get("chunk_count", 1),
        "source_segments": metadata.get("source_segments", 1),
        "protagonist_profile": metadata.get("protagonist_profile"),
        "character_profiles": metadata.get("character_profiles")
        or metadata.get("core_characters")
        or [],
        "heroine_profiles": metadata.get("heroine_profiles")
        or metadata.get("heroine_candidates")
        or [],
        "supporting_profiles": metadata.get("supporting_profiles") or [],
        "location_profiles": metadata.get("location_profiles") or [],
        "faction_profiles": metadata.get("faction_profiles") or [],
        "plot_threads": metadata.get("plot_threads") or [],
        "relationship_highlights": metadata.get("relationship_highlights") or [],
        "worldline_order": metadata.get("worldline_order", []),
        "segment_overview": metadata.get("segment_overview", []),
    }


def graph_from_payload(payload: dict[str, Any]) -> LightweightGraph:
    protagonist_name = _coerce_str(payload.get("protagonist"), "主角待复核")
    if protagonist_name in {"待复核", "待识别", "未知"}:
        protagonist_name = "主角"
    protagonist_profile = _normalize_entity_profile(
        payload.get("protagonist_profile")
        or {
            "name": protagonist_name,
            "entity_type": "character",
            "role": "主角",
            "importance": "lead",
            "is_protagonist": True,
        },
        default_entity_type="character",
        fallback_role="主角",
    )
    if protagonist_profile["name"] in {"", "待复核", "待识别", "未知"}:
        protagonist_profile["name"] = protagonist_name
    protagonist_profile["entity_type"] = "character"
    protagonist_profile["importance"] = "lead"
    protagonist_profile["is_protagonist"] = True
    protagonist_name = protagonist_profile["name"]

    raw_character_profiles: list[dict[str, Any]] = [protagonist_profile]
    raw_character_profiles.extend(payload.get("character_profiles") or [])
    raw_character_profiles.extend(payload.get("heroine_profiles") or [])
    raw_character_profiles.extend(payload.get("supporting_profiles") or [])
    character_profiles = _merge_entity_profiles(
        raw_character_profiles,
        default_entity_type="character",
        fallback_role="身份待复核",
    )

    protagonist_profile = next(
        (item for item in character_profiles if item["name"] == protagonist_name),
        protagonist_profile,
    )
    protagonist_profile["is_protagonist"] = True
    protagonist_profile["importance"] = "lead"

    location_profiles = _merge_entity_profiles(
        payload.get("location_profiles") or [],
        default_entity_type="location",
        fallback_role="地点",
    )
    faction_profiles = _merge_entity_profiles(
        payload.get("faction_profiles") or [],
        default_entity_type="faction",
        fallback_role="势力",
    )
    plot_threads = _merge_plot_threads(payload.get("plot_threads") or [])
    relationships = _merge_relationships(payload.get("relationship_highlights") or [])

    heroine_profiles = _merge_entity_profiles(
        payload.get("heroine_profiles") or [],
        default_entity_type="character",
        fallback_role="身份待复核",
    )
    if not heroine_profiles:
        heroine_profiles = [
            item
            for item in character_profiles
            if item["name"] != protagonist_name and _is_romance_profile(item)
        ]
    heroine_names = {item["name"] for item in heroine_profiles}
    supporting_profiles = _derive_supporting_profiles(
        payload,
        protagonist_name=protagonist_name,
        heroine_names=heroine_names,
        character_profiles=character_profiles,
    )
    worldline_order = _derive_worldline_order(
        payload,
        protagonist_profile,
        character_profiles,
        location_profiles,
        plot_threads,
        _compact_segment_overview(payload.get("segment_overview")),
    )
    segment_overview = _derive_segment_overview(
        payload,
        worldline_order=worldline_order,
        heroine_profiles=heroine_profiles,
        character_profiles=character_profiles,
        location_profiles=location_profiles,
        plot_threads=plot_threads,
    )
    core_characters = _derive_core_characters(
        protagonist_profile,
        heroine_profiles,
        supporting_profiles,
        character_profiles,
    )

    heroine_pool_estimate = max(
        _coerce_int(payload.get("heroine_pool_estimate"), len(heroine_profiles)),
        len(heroine_profiles),
    )
    source_segments = max(_coerce_int(payload.get("source_segments"), 1), 1)
    chunk_count = max(_coerce_int(payload.get("chunk_count"), 1), 1)

    nodes: list[GraphNode] = []
    id_map: dict[str, str] = {}

    def add_node(
        label: str,
        *,
        category: str,
        weight: int,
        chapter_hits: int = 0,
        role: str | None = None,
        evidence: str | None = None,
        tags: list[str] | None = None,
    ) -> None:
        if not label or label in id_map:
            return
        node_id = f"n{len(nodes) + 1}"
        id_map[label] = node_id
        nodes.append(
            GraphNode(
                id=node_id,
                label=label,
                category=category,
                weight=max(weight, 1),
                chapter_hits=max(chapter_hits, 0),
                role=role,
                evidence=evidence,
                tags=tags or [],
            )
        )

    for item in character_profiles:
        category = "主角"
        if item["name"] != protagonist_name:
            category = "关键情感角色" if item["name"] in heroine_names else "人物"
        add_node(
            item["name"],
            category=category,
            weight=item["score"],
            chapter_hits=item["chapter_hits"],
            role=None if item["name"] == protagonist_name else item["role"],
            evidence=item["evidence"],
            tags=item["tags"],
        )

    for item in location_profiles:
        add_node(
            item["name"],
            category="地点",
            weight=item["score"],
            chapter_hits=item["chapter_hits"],
            role=item["role"],
            evidence=item["evidence"],
            tags=item["tags"],
        )

    for item in faction_profiles:
        add_node(
            item["name"],
            category="势力",
            weight=item["score"],
            chapter_hits=item["chapter_hits"],
            role=item["role"],
            evidence=item["evidence"],
            tags=item["tags"],
        )

    for item in plot_threads:
        add_node(
            item["title"],
            category="剧情",
            weight=item["importance"],
            role=item["stage"],
            evidence=item["evidence"],
            tags=item["tags"],
        )

    edge_map: dict[tuple[str, str, str], GraphEdge] = {}
    for item in relationships:
        if item["source"] not in id_map or item["target"] not in id_map:
            continue
        _append_edge(
            edge_map,
            GraphEdge(
                source=id_map[item["source"]],
                target=id_map[item["target"]],
                relation=item["relation"],
                weight=item["weight"],
                chapter_hits=item["chapter_hits"],
                evidence=item["evidence"],
                tags=item["tags"],
            ),
        )

    for item in plot_threads:
        plot_id = id_map.get(item["title"])
        if plot_id is None:
            continue
        for name in item["involved_characters"]:
            target = id_map.get(name)
            if target is None:
                continue
            _append_edge(
                edge_map,
                GraphEdge(
                    source=plot_id,
                    target=target,
                    relation="涉及人物",
                    weight=max(item["importance"] // 10, 1),
                    evidence=item["evidence"],
                    tags=["剧情线"],
                ),
            )
        for name in item["key_locations"]:
            target = id_map.get(name)
            if target is None:
                continue
            _append_edge(
                edge_map,
                GraphEdge(
                    source=plot_id,
                    target=target,
                    relation="发生于",
                    weight=max(item["importance"] // 12, 1),
                    evidence=item["evidence"],
                    tags=["剧情线"],
                ),
            )
        for name in item["related_factions"]:
            target = id_map.get(name)
            if target is None:
                continue
            _append_edge(
                edge_map,
                GraphEdge(
                    source=plot_id,
                    target=target,
                    relation="牵涉势力",
                    weight=max(item["importance"] // 12, 1),
                    evidence=item["evidence"],
                    tags=["剧情线"],
                ),
            )

    return LightweightGraph(
        nodes=nodes,
        edges=list(edge_map.values()),
        metadata={
            "method": _coerce_str(payload.get("method"), "mirofish-llm-graph"),
            "profile_method": _coerce_str(
                payload.get("profile_method"),
                "llm chunk -> story graph -> reduce -> scan",
            ),
            "graph_type": "story_graph",
            "chunk_count": chunk_count,
            "source_segments": source_segments,
            "protagonist": protagonist_name,
            "heroine_pool_estimate": heroine_pool_estimate,
            "protagonist_profile": protagonist_profile,
            "character_profiles": character_profiles[:40],
            "heroine_profiles": heroine_profiles[:16],
            "supporting_profiles": supporting_profiles[:12],
            "heroine_candidates": heroine_profiles[:16],
            "core_characters": core_characters,
            "location_profiles": location_profiles[:20],
            "faction_profiles": faction_profiles[:20],
            "plot_threads": plot_threads[:24],
            "relationship_highlights": relationships[:40],
            "worldline_order": worldline_order,
            "segment_overview": segment_overview[:24],
            "graph_stats": {
                "character_count": len(character_profiles),
                "location_count": len(location_profiles),
                "faction_count": len(faction_profiles),
                "plot_count": len(plot_threads),
                "relationship_count": len(relationships),
            },
        },
    )


def _segment_graph_input(
    graph: LightweightGraph, segment_index: int, segment_total: int
) -> dict[str, Any]:
    payload = _graph_payload(graph)
    payload["segment_index"] = segment_index
    payload["segment_total"] = segment_total
    return payload


def _local_merge_payload(graphs: list[LightweightGraph]) -> dict[str, Any]:
    payloads = [_graph_payload(graph) for graph in graphs]
    protagonist_counter: dict[str, int] = {}
    protagonist_profile: dict[str, Any] | None = None
    heroine_pool_estimate = 0
    chunk_count = 0
    worldline_order: list[str] = []
    segment_overview: list[dict[str, Any]] = []
    heroine_profiles: list[dict[str, Any]] = []
    supporting_profiles: list[dict[str, Any]] = []
    character_profiles: list[dict[str, Any]] = []
    location_profiles: list[dict[str, Any]] = []
    faction_profiles: list[dict[str, Any]] = []
    plot_threads: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []

    for index, payload in enumerate(payloads, start=1):
        protagonist = _coerce_str(payload.get("protagonist"), "主角待复核")
        protagonist_counter[protagonist] = protagonist_counter.get(protagonist, 0) + 1
        if protagonist_profile is None and payload.get("protagonist_profile"):
            protagonist_profile = dict(payload["protagonist_profile"])

        heroine_pool_estimate = max(
            heroine_pool_estimate,
            _coerce_int(payload.get("heroine_pool_estimate"), 0),
        )
        chunk_count += max(_coerce_int(payload.get("chunk_count"), 1), 1)
        worldline_order = _merge_worldline_order(
            worldline_order,
            _coerce_str_list(payload.get("worldline_order")),
        )
        segment_overview.extend(_compact_segment_overview(payload.get("segment_overview")))

        for key, bucket in (
            ("heroine_profiles", heroine_profiles),
            ("supporting_profiles", supporting_profiles),
        ):
            for item in payload.get(key) or []:
                if not isinstance(item, dict):
                    continue
                candidate = dict(item)
                candidate["segment_indexes"] = sorted(
                    set(_coerce_int_list(candidate.get("segment_indexes")) + [index])
                )
                bucket.append(candidate)

        for key, bucket in (
            ("character_profiles", character_profiles),
            ("location_profiles", location_profiles),
            ("faction_profiles", faction_profiles),
            ("plot_threads", plot_threads),
            ("relationship_highlights", relationships),
        ):
            for item in payload.get(key) or []:
                if not isinstance(item, dict):
                    continue
                candidate = dict(item)
                candidate["segment_indexes"] = sorted(
                    set(_coerce_int_list(candidate.get("segment_indexes")) + [index])
                )
                bucket.append(candidate)

    protagonist_name = max(
        protagonist_counter,
        key=lambda key: (protagonist_counter[key], key != "主角待复核"),
        default="主角待复核",
    )
    protagonist_profile = protagonist_profile or {
        "name": protagonist_name,
        "entity_type": "character",
        "role": "主角",
        "importance": "lead",
        "is_protagonist": True,
    }
    protagonist_profile["name"] = protagonist_name
    protagonist_profile["entity_type"] = "character"
    protagonist_profile["importance"] = "lead"
    protagonist_profile["is_protagonist"] = True
    protagonist_profile.setdefault("segment_indexes", list(range(1, len(graphs) + 1)))

    return {
        "protagonist": protagonist_name,
        "heroine_pool_estimate": heroine_pool_estimate,
        "chunk_count": chunk_count,
        "source_segments": len(graphs),
        "protagonist_profile": protagonist_profile,
        "heroine_profiles": _merge_entity_profiles(
            heroine_profiles,
            default_entity_type="character",
            fallback_role="身份待复核",
        )[:16],
        "supporting_profiles": _merge_entity_profiles(
            supporting_profiles,
            default_entity_type="character",
            fallback_role="关键人物",
        )[:12],
        "character_profiles": _merge_entity_profiles(
            character_profiles,
            default_entity_type="character",
            fallback_role="身份待复核",
        )[:40],
        "location_profiles": _merge_entity_profiles(
            location_profiles,
            default_entity_type="location",
            fallback_role="地点",
        )[:20],
        "faction_profiles": _merge_entity_profiles(
            faction_profiles,
            default_entity_type="faction",
            fallback_role="势力",
        )[:20],
        "plot_threads": _merge_plot_threads(plot_threads)[:24],
        "relationship_highlights": _merge_relationships(relationships)[:40],
        "worldline_order": worldline_order,
        "segment_overview": segment_overview[:24],
    }


def _reduce_graph_batch(
    novel_input: NovelInput,
    graphs: list[LightweightGraph],
    *,
    model: str | None = None,
) -> LightweightGraph:
    if len(graphs) == 1:
        return graphs[0]

    prompt_template = read_prompt("graph_reduce.md")
    llm = LLMClient(model=model, profile="graph")
    batch_payload = {
        "title": novel_input.title,
        "segment_count": len(graphs),
        "segment_graphs": [
            _segment_graph_input(graph, index, len(graphs))
            for index, graph in enumerate(graphs, start=1)
        ],
    }
    prompt = prompt_template.format(
        title=novel_input.title,
        graph_json=json.dumps(batch_payload, ensure_ascii=False, indent=2),
    )
    payload = llm.generate_json(system_prompt=SYSTEM_PROMPT, user_prompt=prompt)
    payload["method"] = "mirofish-llm-graph-reduced"
    payload["profile_method"] = "llm segment story graph -> reduce -> scan"
    if "source_segments" not in payload:
        payload["source_segments"] = sum(
            max(_coerce_int(graph.metadata.get("source_segments"), 1), 1) for graph in graphs
        )
    if "chunk_count" not in payload:
        payload["chunk_count"] = sum(
            max(_coerce_int(graph.metadata.get("chunk_count"), 1), 1) for graph in graphs
        )
    return graph_from_payload(payload)


def _should_split_failed_segment(exc: Exception) -> bool:
    message = f"{type(exc).__name__}: {exc}".lower()
    split_tokens = (
        "504",
        "503",
        "502",
        "gateway time-out",
        "gateway timeout",
        "timeout",
        "timed out",
        "connection",
        "jsondecodeerror",
        "invalid control character",
        "unterminated string",
        "expecting property name",
        "expecting ',' delimiter",
    )
    return any(token in message for token in split_tokens)


def _subsegment_input(
    novel_input: NovelInput, text: str, index: int, total: int
) -> NovelInput:
    return type(novel_input)(
        source_path=novel_input.source_path,
        title=f"{novel_input.title} [split {index}/{total}]",
        raw_text=text,
        author=novel_input.author,
        publisher=novel_input.publisher,
        published_at=novel_input.published_at,
        description=novel_input.description,
    )


def build_llm_graph(
    novel_input: NovelInput,
    model: str | None = None,
    *,
    split_token_budget: int = 12000,
    min_split_token_budget: int = 2500,
    split_depth: int = 0,
    max_split_depth: int = 3,
) -> LightweightGraph:
    try:
        return _build_llm_graph_once(novel_input, model=model)
    except Exception as exc:
        estimated_tokens = _estimate_tokens(novel_input.raw_text)
        if (
            split_depth >= max_split_depth
            or estimated_tokens <= max(min_split_token_budget, split_token_budget)
            or not _should_split_failed_segment(exc)
        ):
            raise

        next_budget = max(
            min_split_token_budget,
            min(split_token_budget, max(min_split_token_budget, estimated_tokens // 2)),
        )
        parts = _split_text_for_llm(novel_input.raw_text, next_budget)
        if len(parts) <= 1:
            raise

        next_split_budget = max(min_split_token_budget, next_budget // 2)
        subgraphs: list[LightweightGraph] = []
        for index, text in enumerate(parts, start=1):
            subgraphs.append(
                build_llm_graph(
                    _subsegment_input(novel_input, text, index, len(parts)),
                    model=model,
                    split_token_budget=next_split_budget,
                    min_split_token_budget=min_split_token_budget,
                    split_depth=split_depth + 1,
                    max_split_depth=max_split_depth,
                )
            )

        reduced = reduce_llm_graphs(novel_input, subgraphs, model=model, batch_size=6)
        reduced.metadata["method"] = "mirofish-llm-graph-split-reduced"
        reduced.metadata["profile_method"] = "llm chunk -> auto split reduce -> story graph"
        reduced.metadata["chunk_count"] = sum(
            max(_coerce_int(graph.metadata.get("chunk_count"), 1), 1) for graph in subgraphs
        )
        reduced.metadata["source_segments"] = 1
        return reduced


def reduce_llm_graphs(
    novel_input: NovelInput,
    graphs: list[LightweightGraph],
    *,
    model: str | None = None,
    batch_size: int = 10,
) -> LightweightGraph:
    if not graphs:
        return graph_from_payload({"protagonist": "主角待复核"})
    if len(graphs) == 1:
        return graphs[0]

    current = graphs[:]
    while len(current) > 1:
        reduced: list[LightweightGraph] = []
        for start in range(0, len(current), batch_size):
            chunk = current[start : start + batch_size]
            try:
                reduced.append(_reduce_graph_batch(novel_input, chunk, model=model))
            except Exception:
                reduced.append(graph_from_payload(_local_merge_payload(chunk)))
        current = reduced

    final_payload = _local_merge_payload([current[0]])
    final_payload.update(_graph_payload(current[0]))
    final_payload["source_segments"] = sum(
        max(_coerce_int(graph.metadata.get("source_segments"), 1), 1) for graph in graphs
    )
    final_payload["chunk_count"] = sum(
        max(_coerce_int(graph.metadata.get("chunk_count"), 1), 1) for graph in graphs
    )
    return graph_from_payload(final_payload)


def _build_llm_graph_once(novel_input: NovelInput, model: str | None = None) -> LightweightGraph:
    prompt_template = read_prompt("graph_extract.md")
    requirements = read_resource("scan_requirements.md")
    term_reference = read_resource("term_reference.md")
    prompt = prompt_template.format(
        title=novel_input.title,
        requirements=requirements,
        term_reference=term_reference,
        text_excerpt=novel_input.raw_text,
    )

    llm = LLMClient(model=model, profile="graph")
    payload = llm.generate_json(system_prompt=SYSTEM_PROMPT, user_prompt=prompt)
    protagonist = _coerce_str(payload.get("protagonist"))
    protagonist_profile = payload.get("protagonist_profile") or {}
    summary = _coerce_str(protagonist_profile.get("summary"))
    evidence = _coerce_str(protagonist_profile.get("evidence"))
    character_profiles = payload.get("character_profiles") or []
    heroine_profiles = payload.get("heroine_profiles") or []
    if (
        CHINESE_RE.search(novel_input.raw_text)
        and not character_profiles
        and not heroine_profiles
        and protagonist in {"", "待识别", "待复核"}
        and any(token in f"{summary} {evidence}" for token in ("占位", "????", "???", "待补充"))
    ):
        raise RuntimeError(
            "当前第三方网关虽然可连通，但会损坏中文输入/输出，无法可靠生成中文小说知识图谱。"
            f" base_url={llm.base_url}; model={llm.model}"
        )
    return graph_from_payload(payload)
