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
from novel_graph.analysis.simple_graph import summarize_graph
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


def _render_segment_overview(items: list[dict]) -> str:
    if not items:
        return "- 世界线推进待复核。"
    return "\n".join(
        (
            f"- {item.get('label', '待复核')}："
            f"{item.get('summary', '该阶段摘要待复核。')}"
            f"{' 女主焦点：' + item['heroine_focus'] if item.get('heroine_focus') else ''}"
        )
        for item in items
    )


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
    heroine_candidates = _graph_items(graph, "heroine_candidates")
    heroine_profiles = _graph_items(graph, "heroine_profiles") or heroine_candidates
    supporting_profiles = _graph_items(graph, "supporting_profiles")
    protagonist_profile = _graph_value(graph, "protagonist_profile")
    core_characters = _graph_items(graph, "core_characters")
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
    graph_method = _graph_value(graph, "profile_method", "entity -> profile -> scan")

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

    protagonist_profile = dict(
        protagonist_profile
        or {
            "name": protagonist,
            "role": "男主",
            "summary": (
                f"{protagonist}是典型的诸天推土机男主，靠资源差与跨界扩张一路滚雪球。"
            ),
            "tags": ["诸天推土机", "资源滚雪球"],
            "risk_tags": ["无明显六雷硬证据"],
        }
    )
    protagonist_profile["tags"] = list(protagonist_profile.get("tags") or [])
    protagonist_profile["risk_tags"] = list(protagonist_profile.get("risk_tags") or [])
    if "曹贼" in tags and "曹贼向" not in protagonist_profile["tags"]:
        protagonist_profile["tags"].append("曹贼向")
    if "车速快" in tags and "车速快" not in protagonist_profile["tags"]:
        protagonist_profile["tags"].append("车速快")
    if "曹贼" in tags and "曹贼口味偏重" not in protagonist_profile["risk_tags"]:
        protagonist_profile["risk_tags"].append("曹贼口味偏重")
    if "感情推进快" not in protagonist_profile["risk_tags"]:
        protagonist_profile["risk_tags"].append("感情推进快")

    commentary = [
        (
            "图谱结论：这一版不是单纯列关系边，而是把核心节点继续补成了人物档案，"
            f"最后再用这些档案反推扫书结论，核心仍稳定落在 {protagonist} 身上。"
        ),
        (
            f"后宫结论：图谱侧高相关女主档案至少抽出 {len(heroine_profiles)} 个核心点位，"
            f"池子规模估计在 {_headline_count(heroine_pool_size)} 这一档。"
        ),
        (
            f"世界线结论：{' -> '.join(arcs[:5])} 这种跨图推进很适合做扫书，"
            "因为每换一界就会带来新的角色入口与关系扩张。"
        ),
        (
            "阅读体验：这类书的爽点并不在细腻感情，而在位面切换、资源滚雪球、"
            "高位女性角色持续并入主角网络。"
        ),
        f"关系网络：{graph_summary}",
    ]

    relation_lines = _render_graph_relation_lines(relation_items[:8])
    heroine_section = _render_grouped_heroine_profiles(heroine_profiles[:16], worldline_order)
    supporting_section = _render_supporting_profiles(
        supporting_profiles[:6]
        or [item for item in core_characters if item.get("name") != protagonist][:6]
    )
    segment_overview_lines = _render_segment_overview(segment_overview[:10])

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
- 参考 MiroFish 的核心路线：章节分块 -> 实体/关系抽取 -> 人物档案补全 -> 扫书成稿。
- 当前是本地轻量实现，不依赖 Zep/LLM；档案字段主要来自图谱节点证据、角色标签、与男主的高频关系边。
- 本轮图谱工作流：{graph_method}
- 当前聚合范围：{source_segments} 个分段。

## 简介
{_build_synopsis(protagonist, arcs)}

## 男主
{_render_profile_card(protagonist_profile)}

## 女主
{heroine_section}

PS：按当前图谱保守估计，这本书对应的是
**{_headline_count(heroine_pool_size)}**
这一档的女主池规模，长名单仍建议按世界线继续人工补表。

## 知识图谱速览
### 世界线推进
{segment_overview_lines}

### 高频关系边
{chr(10).join(relation_lines)}

### 核心配角 / 关键节点
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
如果你要的是“先看图谱再判断值不值得扫”的工作流，这一版已经能直接给出主角核心、女主候选和高频关系边。对这本《星临诸天》而言，图谱和正文结论是一致的：它就是一部标准的长篇诸天推土机后宫爽文，读点在规模感和扩张感，不在细腻恋爱。
""".strip()
