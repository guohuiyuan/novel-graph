from __future__ import annotations

import json
import re
from typing import Any

from novel_graph.domain.models import GraphEdge, GraphNode, LightweightGraph, NovelInput
from novel_graph.services.llm_client import LLMClient
from novel_graph.services.prompt_repo import read_prompt, read_resource

SYSTEM_PROMPT = (
    "你是小说知识图谱构建器。"
    "你要参考 MiroFish 的思路：先抽实体与关系，再把核心实体补成人物档案，"
    "最后输出一个扫书可用的结构化 JSON 图谱。"
)

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")
_SPLIT_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")
_CHAPTER_HEADING_RE = re.compile(
    r"^(第[0-9零一二三四五六七八九十百千万两]+[章节卷回幕篇]|chapter\s*\d+|#{1,3}\s+)",
    flags=re.IGNORECASE,
)


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


def _normalize_profile(
    item: dict[str, Any], *, fallback_role: str = "身份待复核"
) -> dict[str, Any]:
    return {
        "name": _coerce_str(item.get("name")),
        "role": _coerce_str(item.get("role"), fallback_role),
        "worldline": _coerce_str(item.get("worldline"), "待复核"),
        "chapter_hits": _coerce_int(item.get("chapter_hits"), 0),
        "score": _coerce_int(item.get("score"), 10),
        "summary": _coerce_str(item.get("summary"), "正文证据不足，人物简介待复核。"),
        "tags": _merge_unique(_coerce_str_list(item.get("tags"))),
        "risk_tags": _merge_unique(
            _coerce_str_list(item.get("risk_tags")) or ["无明显六雷硬证据"]
        ),
        "aliases": _merge_unique(_coerce_str_list(item.get("aliases"))),
        "segment_indexes": _coerce_int_list(item.get("segment_indexes")),
        "evidence": _coerce_str(item.get("evidence"), "正文证据待补"),
        "relation_summary": _coerce_str(item.get("relation_summary")),
    }


def _merge_profiles(
    items: list[dict[str, Any]], *, fallback_role: str = "身份待复核"
) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []

    for raw in items:
        profile = _normalize_profile(raw, fallback_role=fallback_role)
        name = profile["name"]
        if not name:
            continue
        if name not in merged:
            merged[name] = profile
            order.append(name)
            continue

        existing = merged[name]
        existing["chapter_hits"] += profile["chapter_hits"]
        existing["score"] = max(existing["score"], profile["score"])
        if existing["role"] == fallback_role and profile["role"] != fallback_role:
            existing["role"] = profile["role"]
        if existing["worldline"] == "待复核" and profile["worldline"] != "待复核":
            existing["worldline"] = profile["worldline"]
        if existing["summary"] == "正文证据不足，人物简介待复核。" and profile["summary"]:
            existing["summary"] = profile["summary"]
        existing["tags"] = _merge_unique(existing["tags"] + profile["tags"])
        existing["risk_tags"] = _merge_unique(existing["risk_tags"] + profile["risk_tags"])
        existing["aliases"] = _merge_unique(existing["aliases"] + profile["aliases"])
        existing["segment_indexes"] = sorted(
            set(existing["segment_indexes"] + profile["segment_indexes"])
        )
        if existing["evidence"] == "正文证据待补" and profile["evidence"]:
            existing["evidence"] = profile["evidence"]
        if not existing["relation_summary"] and profile["relation_summary"]:
            existing["relation_summary"] = profile["relation_summary"]

    return [merged[name] for name in order]


def _normalize_relationship(item: dict[str, Any]) -> dict[str, Any] | None:
    source = _coerce_str(item.get("source"))
    target = _coerce_str(item.get("target"))
    if not source or not target or source == target:
        return None

    return {
        "source": source,
        "target": target,
        "relation": _coerce_str(item.get("relation"), "同场互动"),
        "chapter_hits": _coerce_int(item.get("chapter_hits"), 0),
        "weight": _coerce_int(item.get("weight"), _coerce_int(item.get("chapter_hits"), 1)),
        "evidence": _coerce_str(item.get("evidence"), "正文证据待补"),
        "tags": _merge_unique(_coerce_str_list(item.get("tags"))),
        "segment_indexes": _coerce_int_list(item.get("segment_indexes")),
    }


def _merge_relationships(items: list[dict[str, Any]]) -> list[dict]:
    merged: dict[tuple[str, str, str], dict[str, Any]] = {}
    order: list[tuple[str, str, str]] = []

    for raw in items:
        relation = _normalize_relationship(raw)
        if relation is None:
            continue

        key = (relation["source"], relation["target"], relation["relation"])
        if key not in merged:
            merged[key] = relation
            order.append(key)
            continue

        existing = merged[key]
        existing["chapter_hits"] += relation["chapter_hits"]
        existing["weight"] += relation["weight"]
        existing["tags"] = _merge_unique(existing["tags"] + relation["tags"])
        existing["segment_indexes"] = sorted(
            set(existing["segment_indexes"] + relation["segment_indexes"])
        )
        if existing["evidence"] == "正文证据待补" and relation["evidence"]:
            existing["evidence"] = relation["evidence"]

    return [merged[key] for key in order]


def _compact_segment_overview(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []

    overviews: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        label = _coerce_str(item.get("label") or item.get("worldline"))
        summary = _coerce_str(item.get("summary"))
        heroine_focus = _coerce_str(item.get("heroine_focus"))
        if not any((label, summary, heroine_focus)):
            continue
        overviews.append(
            {
                "label": label or "待复核",
                "summary": summary or "段落摘要待复核。",
                "heroine_focus": heroine_focus,
            }
        )
    return overviews


def _graph_payload(graph: LightweightGraph) -> dict[str, Any]:
    metadata = graph.metadata or {}
    return {
        "protagonist": metadata.get("protagonist"),
        "heroine_pool_estimate": metadata.get("heroine_pool_estimate", 0),
        "chunk_count": metadata.get("chunk_count", 1),
        "protagonist_profile": metadata.get("protagonist_profile"),
        "heroine_profiles": metadata.get("heroine_profiles")
        or metadata.get("heroine_candidates"),
        "supporting_profiles": metadata.get("supporting_profiles")
        or metadata.get("core_characters"),
        "relationship_highlights": metadata.get("relationship_highlights"),
        "worldline_order": metadata.get("worldline_order", []),
        "segment_overview": metadata.get("segment_overview", []),
        "source_segments": metadata.get("source_segments", 1),
    }


def graph_from_payload(payload: dict[str, Any]) -> LightweightGraph:
    protagonist_name = _coerce_str(payload.get("protagonist"), "主角待复核")
    protagonist_profile = _normalize_profile(
        payload.get("protagonist_profile") or {"name": protagonist_name, "role": "男主"},
        fallback_role="男主",
    )
    if protagonist_profile["name"] == "":
        protagonist_profile["name"] = protagonist_name
    protagonist_name = protagonist_profile["name"]

    heroine_profiles = _merge_profiles(payload.get("heroine_profiles") or [])
    supporting_profiles = _merge_profiles(payload.get("supporting_profiles") or [])
    relationships = _merge_relationships(payload.get("relationship_highlights") or [])
    worldline_order = _merge_unique(_coerce_str_list(payload.get("worldline_order")))
    segment_overview = _compact_segment_overview(payload.get("segment_overview"))
    source_segments = max(_coerce_int(payload.get("source_segments"), 1), 1)

    heroine_names = {item["name"] for item in heroine_profiles}
    profile_by_name: dict[str, dict] = {protagonist_name: protagonist_profile}
    for item in heroine_profiles + supporting_profiles:
        profile_by_name.setdefault(item["name"], item)

    for relation in relationships:
        for name in (relation["source"], relation["target"]):
            profile_by_name.setdefault(
                name,
                _normalize_profile({"name": name, "score": 6, "evidence": relation["evidence"]}),
            )

    ordered_names = [protagonist_name]
    ordered_names.extend(
        item["name"] for item in heroine_profiles if item["name"] != protagonist_name
    )
    ordered_names.extend(
        item["name"]
        for item in supporting_profiles
        if item["name"] not in heroine_names and item["name"] != protagonist_name
    )
    ordered_names.extend(name for name in profile_by_name if name not in ordered_names)

    nodes: list[GraphNode] = []
    for index, name in enumerate(ordered_names, start=1):
        profile = profile_by_name[name]
        if name == protagonist_name:
            category = "主角"
        elif name in heroine_names:
            category = "女主候选"
        else:
            category = "核心角色"

        nodes.append(
            GraphNode(
                id=f"n{index}",
                label=name,
                category=category,
                weight=max(profile["score"], 1),
                chapter_hits=max(profile["chapter_hits"], 0),
                role=None if name == protagonist_name else profile["role"],
                evidence=profile["evidence"],
                tags=profile["tags"],
            )
        )

    id_map = {node.label: node.id for node in nodes}
    edges = [
        GraphEdge(
            source=id_map[item["source"]],
            target=id_map[item["target"]],
            relation=item["relation"],
            weight=max(item["weight"], 1),
            chapter_hits=max(item["chapter_hits"], 0),
            evidence=item["evidence"],
            tags=item["tags"],
        )
        for item in relationships
        if item["source"] in id_map and item["target"] in id_map
    ]

    heroine_pool_estimate = max(
        _coerce_int(payload.get("heroine_pool_estimate"), len(heroine_profiles)),
        len(heroine_profiles),
    )
    core_characters = [protagonist_profile] + heroine_profiles[:4] + supporting_profiles[:2]
    core_characters = core_characters[:6]

    return LightweightGraph(
        nodes=nodes,
        edges=edges,
        metadata={
            "method": _coerce_str(payload.get("method"), "mirofish-llm-graph"),
            "profile_method": _coerce_str(
                payload.get("profile_method"),
                "llm entity -> profile -> scan",
            ),
            "chunk_count": max(_coerce_int(payload.get("chunk_count"), 1), 1),
            "source_segments": source_segments,
            "protagonist": protagonist_name,
            "heroine_pool_estimate": heroine_pool_estimate,
            "protagonist_profile": protagonist_profile,
            "heroine_profiles": heroine_profiles,
            "supporting_profiles": supporting_profiles,
            "heroine_candidates": heroine_profiles,
            "core_characters": core_characters,
            "worldline_order": worldline_order,
            "segment_overview": segment_overview,
            "relationship_highlights": relationships[:8],
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
    segment_overview: list[dict[str, str]] = []
    heroine_profiles: list[dict[str, Any]] = []
    supporting_profiles: list[dict[str, Any]] = []
    relationships: list[dict[str, Any]] = []

    for index, payload in enumerate(payloads, start=1):
        protagonist = _coerce_str(payload.get("protagonist"), "主角待复核")
        protagonist_counter[protagonist] = protagonist_counter.get(protagonist, 0) + 1
        if protagonist_profile is None and payload.get("protagonist_profile"):
            protagonist_profile = payload["protagonist_profile"]

        heroine_pool_estimate = max(
            heroine_pool_estimate,
            _coerce_int(payload.get("heroine_pool_estimate"), 0),
        )
        chunk_count += max(_coerce_int(payload.get("chunk_count"), 1), 1)
        worldline_order = _merge_unique(
            worldline_order + _coerce_str_list(payload.get("worldline_order"))
        )
        segment_overview.extend(_compact_segment_overview(payload.get("segment_overview")))

        for item in payload.get("heroine_profiles") or []:
            if isinstance(item, dict):
                candidate = dict(item)
                candidate["segment_indexes"] = sorted(
                    set(_coerce_int_list(candidate.get("segment_indexes")) + [index])
                )
                heroine_profiles.append(candidate)
        for item in payload.get("supporting_profiles") or []:
            if isinstance(item, dict):
                candidate = dict(item)
                candidate["segment_indexes"] = sorted(
                    set(_coerce_int_list(candidate.get("segment_indexes")) + [index])
                )
                supporting_profiles.append(candidate)
        for item in payload.get("relationship_highlights") or []:
            if isinstance(item, dict):
                candidate = dict(item)
                candidate["segment_indexes"] = sorted(
                    set(_coerce_int_list(candidate.get("segment_indexes")) + [index])
                )
                relationships.append(candidate)

    protagonist_name = max(
        protagonist_counter,
        key=lambda key: (protagonist_counter[key], key != "主角待复核"),
        default="主角待复核",
    )
    protagonist_profile = protagonist_profile or {"name": protagonist_name, "role": "男主"}
    protagonist_profile["name"] = protagonist_name
    if "segment_indexes" not in protagonist_profile:
        protagonist_profile["segment_indexes"] = list(range(1, len(graphs) + 1))

    heroine_profiles = _merge_profiles(heroine_profiles)
    supporting_profiles = _merge_profiles(supporting_profiles)
    relationships = _merge_relationships(relationships)
    heroine_pool_estimate = max(heroine_pool_estimate, len(heroine_profiles))

    return {
        "protagonist": protagonist_name,
        "heroine_pool_estimate": heroine_pool_estimate,
        "chunk_count": chunk_count,
        "source_segments": len(graphs),
        "protagonist_profile": protagonist_profile,
        "heroine_profiles": heroine_profiles[:16],
        "supporting_profiles": supporting_profiles[:10],
        "relationship_highlights": relationships[:16],
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
    llm = LLMClient(model=model)
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
    payload["profile_method"] = "llm segment graph -> reduce -> scan"
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
        reduced.metadata["profile_method"] = "llm extract -> auto split reduce -> scan"
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

    llm = LLMClient(model=model)
    payload = llm.generate_json(system_prompt=SYSTEM_PROMPT, user_prompt=prompt)
    protagonist = _coerce_str(payload.get("protagonist"))
    protagonist_profile = payload.get("protagonist_profile") or {}
    summary = _coerce_str(protagonist_profile.get("summary"))
    evidence = _coerce_str(protagonist_profile.get("evidence"))
    heroine_profiles = payload.get("heroine_profiles") or []
    if (
        CHINESE_RE.search(novel_input.raw_text)
        and not heroine_profiles
        and protagonist in {"", "待识别", "待复核"}
        and any(token in f"{summary} {evidence}" for token in ("占位符", "????", "???", "待补充"))
    ):
        raise RuntimeError(
            "当前第三方网关虽然可连通，但会损坏中文输入/输出，无法可靠生成中文网文知识图谱。"
            f" base_url={llm.base_url}; model={llm.model}"
        )
    return graph_from_payload(payload)
