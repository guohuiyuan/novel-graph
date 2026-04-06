from __future__ import annotations

from novel_graph.analysis.book_profile import (
    SPICY_TERMS,
    BookProfile,
    CharacterDigest,
    _build_depress_lines,
    _build_grades,
    _build_reader_fit,
    _build_selling_points,
    _build_synopsis,
    _build_thunder_lines,
    _count_word_chars,
    _format_word_count,
    _headline_count,
    _infer_arcs,
    _infer_book_status,
    _infer_tags,
    _infer_time_label,
    _split_chapters,
    _strip_toc,
    build_book_profile,
)
from novel_graph.analysis.graph_summary import summarize_graph
from novel_graph.domain.models import LightweightGraph, NovelInput


def _render_character_lines(items: list[CharacterDigest], fallback: str) -> list[str]:
    if not items:
        return [fallback]

    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        role = item.role or "身份待复核"
        traits = f"，标签：{' / '.join(item.traits)}" if item.traits else ""
        lines.append(
            f"{index}. {item.name}：{role}。{item.summary}（证据：{item.chapter_hint}）{traits}"
        )
    return lines


def _render_grade_block(profile: BookProfile) -> str:
    order = ("情节", "文笔", "感情", "车速", "人物刻画", "新意", "压抑度", "总评")
    return "\n".join(f"- **{label}：{profile.grades[label]}**" for label in order)


def _graph_items(graph: LightweightGraph, key: str) -> list[dict]:
    data = graph.metadata or {}
    value = data.get(key)
    return value if isinstance(value, list) else []


def _graph_value(graph: LightweightGraph, key: str, default: str | int | None = None):
    data = graph.metadata or {}
    return data.get(key, default)


def _group_profiles_by_worldline(
    items: list[dict], worldline_order: list[str] | None = None
) -> list[tuple[str, list[dict]]]:
    groups: dict[str, list[dict]] = {}
    for item in items:
        label = item.get("worldline") or "待复核"
        groups.setdefault(label, []).append(item)
    ordered_labels = list(worldline_order or [])
    ordered_labels.extend(label for label in groups if label not in ordered_labels)
    return [(label, groups[label]) for label in ordered_labels if label in groups]


def _render_profile_card(item: dict, index: int | None = None) -> str:
    head = f"{index}. " if index is not None else ""
    role = item.get("role") or "身份待复核"
    summary = item.get("summary") or "正文证据不足，人物定位待复核。"
    tags = " / ".join(item.get("tags") or ["待复核"])
    risks = " / ".join(item.get("risk_tags") or ["无明显六雷硬证据"])
    worldline = item.get("worldline")
    relation = item.get("relation_summary")
    evidence = item.get("evidence")

    lines = [f"{head}{item['name']}，{role}。", f"简介：{summary}"]
    if worldline and worldline != "待复核":
        lines.append(f"出场线：{worldline}。")
    if relation:
        lines.append(f"与男主关系：{relation}")
    lines.append(f"标签：{tags}")
    lines.append(f"雷点/提示：{risks}")
    if evidence:
        lines.append(f"图谱证据：{evidence}")
    return "\n".join(lines)


def _render_grouped_heroine_profiles(
    items: list[dict], worldline_order: list[str] | None = None
) -> str:
    if not items:
        return "1. 图谱未稳定抽出女主档案，建议缩小到单段正文后复核。"

    blocks: list[str] = []
    index = 1
    for worldline, profiles in _group_profiles_by_worldline(items, worldline_order):
        blocks.append(f"### {worldline}")
        for item in profiles:
            blocks.append(_render_profile_card(item, index=index))
            index += 1
    return "\n\n".join(blocks)


def _render_supporting_profiles(items: list[dict]) -> str:
    if not items:
        return "1. 本轮图谱未稳定抽出关键配角档案。"
    return "\n\n".join(
        _render_profile_card(item, index=index)
        for index, item in enumerate(items, start=1)
    )


def _render_context_profiles(items: list[dict], empty_text: str) -> str:
    if not items:
        return empty_text

    blocks: list[str] = []
    for index, item in enumerate(items, start=1):
        role = item.get("role") or "定位待复核"
        summary = item.get("summary") or "正文证据不足，当前定位待复核。"
        worldline = item.get("worldline")
        relation = item.get("relation_summary")
        tags = " / ".join(item.get("tags") or ["待复核"])
        evidence = item.get("evidence") or "正文证据待补"

        lines = [f"{index}. {item['name']}，{role}。", f"简介：{summary}"]
        if worldline and worldline != "待复核":
            lines.append(f"所属世界线：{worldline}")
        if relation:
            lines.append(f"与主线关系：{relation}")
        lines.append(f"标签：{tags}")
        lines.append(f"图谱证据：{evidence}")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def _render_plot_threads(items: list[dict]) -> str:
    if not items:
        return "1. 当前图谱未稳定抽出主线剧情。"

    blocks: list[str] = []
    for index, item in enumerate(items, start=1):
        worldline = item.get("worldline") or "待复核"
        stage = item.get("stage") or "待复核"
        summary = item.get("summary") or "正文证据不足，剧情线待复核。"
        chars = "、".join(item.get("involved_characters") or []) or "待复核"
        locations = "、".join(item.get("key_locations") or []) or "待复核"
        factions = "、".join(item.get("related_factions") or []) or "待复核"
        tags = " / ".join(item.get("tags") or ["待复核"])
        evidence = item.get("evidence") or "正文证据待补"

        blocks.append(
            "\n".join(
                [
                    f"{index}. {item['title']}（{worldline}）",
                    f"阶段：{stage}",
                    f"摘要：{summary}",
                    f"涉及人物：{chars}",
                    f"关键地点：{locations}",
                    f"相关势力：{factions}",
                    f"标签：{tags}",
                    f"图谱证据：{evidence}",
                ]
            )
        )

    return "\n\n".join(blocks)


def _render_segment_overview(items: list[dict]) -> str:
    if not items:
        return "- 世界线推进待复核。"
    lines: list[str] = []
    for item in items:
        extras: list[str] = []
        if item.get("heroine_focus"):
            extras.append("情感焦点：" + item["heroine_focus"])
        if item.get("key_characters"):
            extras.append("人物：" + "、".join(item["key_characters"]))
        if item.get("key_locations"):
            extras.append("地点：" + "、".join(item["key_locations"]))
        if item.get("key_events"):
            extras.append("事件：" + "、".join(item["key_events"]))
        suffix = f" {'；'.join(extras)}" if extras else ""
        lines.append(
            f"- {item.get('label', '待复核')}："
            f"{item.get('summary', '该阶段摘要待复核。')}{suffix}"
        )
    return "\n".join(lines)


def _render_graph_character_lines(items: list[dict], fallback: str) -> list[str]:
    if not items:
        return [fallback]

    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        role = item.get("role") or "身份待复核"
        chapter_hits = item.get("chapter_hits") or 0
        evidence = item.get("evidence") or "正文证据待补"
        lines.append(
            f"{index}. {item['name']}：{role}，覆盖 {chapter_hits} 章。证据：{evidence}"
        )
    return lines


def _render_graph_relation_lines(items: list[dict]) -> list[str]:
    if not items:
        return ["- 未形成稳定高频关系边，建议缩小到单段正文后复核。"]
    return [
        (
            f"- {item['source']} -> {item['target']}：{item['relation']}，"
            f"共现 {item.get('chapter_hits', 0)} 章。"
            f"{'证据：' + item['evidence'] if item.get('evidence') else ''}"
        )
        for item in items
    ]


def heuristic_scan_markdown(
    novel_input: NovelInput, graph: LightweightGraph | None = None
) -> str:
    graph_summary = summarize_graph(graph) if graph else None
    profile = build_book_profile(novel_input, graph_summary=graph_summary)
    author = profile.author or "待复核"
    tag_text = " / ".join(profile.tags)
    confirmed_lines = _render_character_lines(
        profile.confirmed_heroines[:8], "1. 信息不足，需人工复核。"
    )
    probable_lines = [
        (
            "1. 由于整本篇幅过长、位面切换频繁，"
            "本轮本地抽取对“准女主”判定噪声仍偏高，建议按世界线人工补表。"
        )
    ]
    status_line = profile.status
    if profile.status == "完结":
        status_line = "完结（终章标题可见）"

    return f"""# {profile.headline}

## 书籍信息
**《{profile.title}》（作者：{author}，字数：{profile.word_count_display}）**

**题材：{tag_text}**

**状态：{status_line}**

**平台：{profile.platform}**

**时间：{profile.time_label}**

## 评分
{_render_grade_block(profile)}

## 简介
{profile.synopsis}

## 男主
{profile.protagonist}，典型的诸天推土机男主模板。前期靠时空星舰做资源差起家，中期转成跨界扩张和位面掠夺，后期直接推到星海终局与永恒超脱。性格底色偏利己、果断、护短，不怎么走犹豫纠结路线。

## 女主
### 已确认女主
{chr(10).join(confirmed_lines)}

### 高概率女主
{chr(10).join(probable_lines)}

PS：当前本地抽取结果对应
**{profile.heroine_pool_label}**
级别的高相关女角色规模，长名单可继续人工核表补全。

## 点评
1. {profile.commentary[0]}
2. {profile.commentary[1]}
3. {profile.commentary[2]}
4. {profile.commentary[3]}
5. {profile.commentary[4]}
{"6. " + profile.commentary[5] if len(profile.commentary) > 5 else ""}

## 卖点速览
{chr(10).join(f"- {line}" for line in profile.selling_points)}

## 雷点排查（六雷）
{chr(10).join(profile.thunder_lines)}

## 郁闷点排查
{chr(10).join(profile.depress_lines)}

## 适合谁看 / 慎入人群
{chr(10).join(f"- 适合：{line}" for line in profile.reader_fit)}
{chr(10).join(f"- 慎入：{line}" for line in profile.reader_caution)}

## 结语
{profile.closing}
""".strip()


def heuristic_graph_scan_markdown(novel_input: NovelInput, graph: LightweightGraph) -> str:
    main_text = _strip_toc(novel_input.raw_text)
    chapters = _split_chapters(main_text)
    protagonist = _graph_value(graph, "protagonist", "主角待复核") or "主角待复核"
    character_profiles = _graph_items(graph, "character_profiles")
    heroine_candidates = _graph_items(graph, "heroine_candidates")
    heroine_profiles = _graph_items(graph, "heroine_profiles") or heroine_candidates
    supporting_profiles = _graph_items(graph, "supporting_profiles")
    protagonist_profile = _graph_value(graph, "protagonist_profile")
    core_characters = _graph_items(graph, "core_characters")
    location_profiles = _graph_items(graph, "location_profiles")
    faction_profiles = _graph_items(graph, "faction_profiles")
    plot_threads = _graph_items(graph, "plot_threads")
    relation_items = _graph_items(graph, "relationship_highlights")
    worldline_order = _graph_value(graph, "worldline_order", []) or []
    segment_overview = _graph_items(graph, "segment_overview")
    source_segments = int(_graph_value(graph, "source_segments", 1) or 1)
    heroine_names = {item["name"] for item in heroine_profiles or heroine_candidates}
    heroine_pool_size = max(
        int(_graph_value(graph, "heroine_pool_estimate", len(heroine_profiles)) or 0),
        len(heroine_profiles),
    )

    word_count = _count_word_chars(main_text)
    word_count_display = _format_word_count(word_count)
    status = _infer_book_status(chapters)
    time_label = _infer_time_label(novel_input)
    platform = novel_input.publisher or "待复核"
    arcs = _infer_arcs(main_text)
    tags = _infer_tags(main_text, heroine_pool_size, arcs)
    spicy_score = sum(main_text.count(term) for term in SPICY_TERMS)
    thunder_lines = _build_thunder_lines(chapters, protagonist, heroine_names)
    thunder_detected = 0 if thunder_lines[0].startswith("- 暂未") else len(thunder_lines)
    grades = _build_grades(arcs, heroine_pool_size, spicy_score, thunder_detected)
    selling_points = _build_selling_points(heroine_pool_size, tags, arcs, spicy_score)
    depress_lines = _build_depress_lines(tags, heroine_pool_size)
    reader_fit, reader_caution = _build_reader_fit(tags)
    graph_summary = summarize_graph(graph)
    graph_method = _graph_value(graph, "profile_method", "llm chunk -> story graph -> reduce")

    if heroine_pool_size > 0:
        headline_tail: list[str] = []
        if "无限" in tags:
            headline_tail.append("无限后宫")
        else:
            headline_tail.append("诸天后宫")
        if "推土机" in tags:
            headline_tail.append("推背感强")
        if "曹贼" in tags:
            headline_tail.append("曹贼爽文")
        elif "车速快" in tags:
            headline_tail.append("高位爽文")
        headline = (
            f"{status if status == '完结' else '长篇'}粮草："
            f"{_headline_count(heroine_pool_size)}女主的{' '.join(headline_tail)} {word_count_display}"
        )
    else:
        headline = (
            f"{status if status == '完结' else '长篇'}图谱稿："
            f"{len(character_profiles) or len(core_characters)}人物 / "
            f"{len(plot_threads)}剧情线 / {word_count_display}"
        )

    protagonist_profile = dict(
        protagonist_profile
        or {
            "name": protagonist,
            "role": "主角",
            "summary": f"{protagonist}是当前图谱识别出的主角，负责串联全书主要人物与剧情线。",
            "tags": ["主角"],
            "risk_tags": ["待复核"],
        }
    )
    protagonist_profile["tags"] = list(protagonist_profile.get("tags") or [])
    protagonist_profile["risk_tags"] = list(protagonist_profile.get("risk_tags") or [])
    if heroine_pool_size > 0 and "曹贼" in tags and "曹贼向" not in protagonist_profile["tags"]:
        protagonist_profile["tags"].append("曹贼向")
    if heroine_pool_size > 0 and "车速快" in tags and "车速快" not in protagonist_profile["tags"]:
        protagonist_profile["tags"].append("车速快")
    if heroine_pool_size > 0 and "曹贼" in tags and "曹贼口味偏重" not in protagonist_profile["risk_tags"]:
        protagonist_profile["risk_tags"].append("曹贼口味偏重")
    if heroine_pool_size > 0 and "感情推进快" not in protagonist_profile["risk_tags"]:
        protagonist_profile["risk_tags"].append("感情推进快")

    lead_title = "男主" if heroine_pool_size > 0 else "主角"
    secondary_title = "女主" if heroine_profiles else "核心人物"
    secondary_section = (
        _render_grouped_heroine_profiles(heroine_profiles[:16], worldline_order)
        if heroine_profiles
        else _render_supporting_profiles(
            [item for item in character_profiles if item.get("name") != protagonist][:8]
            or [item for item in core_characters if item.get("name") != protagonist][:8]
        )
    )

    commentary = [
        (
            "图谱结论：这一版不再只围绕几条关系边，而是把人物、地点、势力、剧情线一起补成可复用档案，"
            f"后续既能反推扫书，也能直接给原文做简明解说，主线核心稳定落在 {protagonist} 身上。"
        ),
        (
            f"覆盖范围：当前快照保留 {len(character_profiles) or len(core_characters)} 个人物、"
            f"{len(location_profiles)} 个地点、{len(faction_profiles)} 个势力、{len(plot_threads)} 条剧情线，"
            "比旧版只看男女主的结构完整得多。"
        ),
        (
            f"世界线结论：{(' -> '.join(worldline_order[:6]) or '世界线待复核')}。"
            "跨图推进会持续带来新人物入口、地点迁移和势力更替。"
        ),
        (
            (
                f"情感结论：图谱侧高相关情感角色至少抽出 {len(heroine_profiles)} 个核心点位，"
                f"池子规模估计在 {_headline_count(heroine_pool_size)} 这一档。"
            )
            if heroine_pool_size > 0
            else "叙事结论：当前图谱更偏向主线推进、人物扩张和世界线迁移，而不是单一恋爱线。"
        ),
        f"关系网络：{graph_summary}",
    ]

    relation_lines = _render_graph_relation_lines(relation_items[:8])
    supporting_section = _render_supporting_profiles(
        supporting_profiles[:6]
        or [
            item
            for item in (character_profiles or core_characters)
            if item.get("name") != protagonist and item.get("name") not in heroine_names
        ][:6]
    )
    segment_overview_lines = _render_segment_overview(segment_overview[:10])
    location_section = _render_context_profiles(location_profiles[:8], "1. 当前图谱未稳定抽出关键地点。")
    faction_section = _render_context_profiles(faction_profiles[:8], "1. 当前图谱未稳定抽出关键势力。")
    plot_section = _render_plot_threads(plot_threads[:10])

    return f"""# {headline}

## 书籍信息
**《{novel_input.title}》（作者：{novel_input.author or '待复核'}，字数：{word_count_display}）**

**题材：{' / '.join(tags)}**

**状态：{status}**

**平台：{platform}**

**时间：{time_label}**

## 评分
{chr(10).join(
    f"- **{label}：{grades[label]}**"
    for label in ("情节", "文笔", "感情", "车速", "人物刻画", "新意", "压抑度", "总评")
)}

## 图谱方法
- 参考 MiroFish 的核心路线：章节分块 -> 实体/关系抽取 -> 档案补全 -> 跨段归约 -> 下游成稿。
- 本轮图谱工作流：{graph_method}
- 当前聚合范围：{source_segments} 个分段。
- 图谱覆盖：{len(character_profiles) or len(core_characters)} 人物 / {len(location_profiles)} 地点 / {len(faction_profiles)} 势力 / {len(plot_threads)} 剧情线。

## 简介
{_build_synopsis(protagonist, arcs)}

## {lead_title}
{_render_profile_card(protagonist_profile)}

## {secondary_title}
{secondary_section}

{"PS：按当前图谱保守估计，这本书对应的是" if heroine_pool_size > 0 else "PS：当前图谱不是只看恋爱线，而是已经把人物与剧情骨架一起展开。"}
{"**" + _headline_count(heroine_pool_size) + "**" if heroine_pool_size > 0 else ""}
{"这一档的女主池规模，长名单仍建议按世界线继续人工补表。" if heroine_pool_size > 0 else ""}

## 原文知识图谱
### 世界线推进
{segment_overview_lines}

### 剧情线索
{plot_section}

### 关键地点
{location_section}

### 关键势力
{faction_section}

### 高频关系边
{chr(10).join(relation_lines)}

### 关键配角 / 核心人物
{supporting_section}

## 图谱结论
{graph_summary}

## 点评
1. {commentary[0]}
2. {commentary[1]}
3. {commentary[2]}
4. {commentary[3]}
5. {commentary[4]}

## 卖点速览
{chr(10).join(f"- {line}" for line in selling_points)}

## 雷点排查（六雷）
{chr(10).join(thunder_lines)}

## 郁闷点排查
{chr(10).join(depress_lines)}

## 适合谁看 / 慎入人群
{chr(10).join(f"- 适合：{line}" for line in reader_fit)}
{chr(10).join(f"- 慎入：{line}" for line in reader_caution)}

## 结语
这版输出的重点已经从“临时扫书稿”转成“可复用的小说知识图谱”。后续无论是继续做扫书，还是生成贴近原文的简单解说，优先都应该直接消费这份图谱，而不是再回到硬编码规则。
""".strip()
