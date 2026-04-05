from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

from novel_graph.analysis.book_profile import PERSON_STOP_WORDS, ROLE_STOP_WORDS
from novel_graph.domain.models import GraphEdge, GraphNode, LightweightGraph

CHAPTER_HEADING_RE = re.compile(
    r"^(第[0-9零一二三四五六七八九十百千两]+[章节卷回幕篇]|chapter\s*\d+)"
    r"(?:[:：\s].*)?$",
    flags=re.IGNORECASE,
)
NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,4}")
SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？；!?])|\n+")

STOP_WORDS = {
    "自己",
    "我们",
    "你们",
    "他们",
    "她们",
    "可以",
    "已经",
    "就是",
    "都是",
    "不过",
    "而且",
    "只是",
    "能够",
    "这个",
    "那个",
    "一个",
    "一种",
    "还有",
    "没有",
    "因为",
    "所以",
    "如果",
    "然后",
    "虽然",
    "为了",
    "这样",
    "那样",
    "开始",
    "后来",
    "现在",
    "依旧",
    "终于",
    "继续",
    "必须",
    "需要",
    "应该",
    "不会",
    "不能",
    "不是",
    "事情",
    "时候",
    "一下",
    "一次",
    "同时",
    "其中",
    "顿时",
    "立刻",
    "甚至",
    "毕竟",
    "如今",
    "此刻",
    "这时",
    "那时",
    "显然",
    "完全",
    "或许",
    "正在",
    "作为",
    "若是",
    "让他",
    "选择",
    "关系",
    "麻烦",
    "发现",
    "一声",
    "一眼",
    "陨落",
    "拒绝",
    "优势",
    "交易",
    "回归",
    "轻轻",
    "陛下",
    "殿下",
    "公子",
    "小姐",
    "王爷",
    "皇帝",
    "国王",
    "公主",
    "皇后",
    "皇女",
    "女皇",
    "圣女",
    "神女",
    "师尊",
    "道侣",
    "侍女",
    "侍妾",
    "夫人",
    "表妹",
    "秘书",
    "助理",
    "舰灵",
    "说着",
    "地道",
    "当然",
    "之后",
    "下来",
    "起来",
    "什么",
    "所以",
    "过来",
    "出来",
    "好吧",
    "点头",
    "的话",
    "时间",
    "问题",
    "东西",
    "而已",
    "好了",
    "人类文明",
    "星舰中枢",
    "世界本源",
    "太虚星空",
    "权限提升",
    "资源",
    "世界",
    "文明",
    "位面",
    "星空",
    "帝国",
    "联盟",
    "主角",
    "女主",
    "故事",
    "小说",
    "章节",
}
STOP_WORDS.update(PERSON_STOP_WORDS)
STOP_WORDS.update(ROLE_STOP_WORDS)

COMMON_FUNCTION_CHARS = set(
    "自己我们你们他们她们可以已经就是都是不过而且只是能够这个那个一个一种还有没有"
    "因为所以如果然后虽然为了这样那样开始后来现在依旧终于继续必须需要应该不会不能不是"
    "事情时候一下一次同时其中顿时立刻甚至毕竟如今此刻这时那时显然完全还是只要因此至于"
    "微微以后可是出现或许正在作为若是让他选择陛下公子小姐王爷皇帝国王"
)

GENERIC_SUFFIXES = (
    "世界",
    "文明",
    "联盟",
    "帝国",
    "王朝",
    "星宫",
    "星舰",
    "星空",
    "本源",
    "权限",
    "资源",
    "修为",
    "气数",
    "命格",
    "系统",
)
ORDINAL_PREFIXES = ("第一", "第二", "第三", "第四", "第五")

ANCHOR_PREFIXES = (
    "叫",
    "名叫",
    "名为",
    "是",
    "对",
    "与",
    "和",
    "将",
    "把",
    "见到",
    "看见",
    "望着",
    "身边的",
    "面前的",
)
ANCHOR_SUFFIXES = (
    "说道",
    "问道",
    "笑道",
    "答道",
    "冷笑",
    "点头",
    "开口",
    "吩咐",
    "看着",
    "身边",
    "身后",
    "现身",
    "出手",
)

FEMALE_HINTS = (
    "少女",
    "女子",
    "女人",
    "美人",
    "美妇",
    "佳人",
    "公主",
    "皇后",
    "皇女",
    "女皇",
    "圣女",
    "神女",
    "师尊",
    "道侣",
    "侍女",
    "侍妾",
    "夫人",
    "表妹",
    "闺蜜",
    "秘书",
    "助理",
    "舰灵",
)
ROMANCE_HINTS = (
    "喜欢",
    "爱意",
    "倾心",
    "心动",
    "暧昧",
    "亲吻",
    "婚约",
    "联姻",
    "侍寝",
    "侍妾",
    "侍女",
    "圆房",
    "房中",
    "双修",
    "宠幸",
    "献身",
    "妻子",
    "王妃",
    "皇后",
    "道侣",
    "怀孕",
)
CONFLICT_HINTS = (
    "杀",
    "斩",
    "敌对",
    "围攻",
    "追杀",
    "镇压",
    "冲突",
    "翻脸",
    "对峙",
    "仇",
    "反目",
)
ROLE_KEYWORDS = (
    "舰灵",
    "世界意志",
    "位面意志",
    "女皇",
    "皇后",
    "皇女",
    "公主",
    "王妃",
    "圣女",
    "神女",
    "师尊",
    "道侣",
    "侍女",
    "侍妾",
    "夫人",
    "表妹",
    "秘书",
    "助理",
    "宫主",
    "宗主",
)
FEMALE_ROLES = {
    "舰灵",
    "世界意志",
    "位面意志",
    "女皇",
    "皇后",
    "皇女",
    "公主",
    "王妃",
    "圣女",
    "神女",
    "师尊",
    "道侣",
    "侍女",
    "侍妾",
    "夫人",
    "表妹",
    "秘书",
    "助理",
    "宫主",
    "宗主",
}

NAME_ANCHOR_PATTERNS = (
    re.compile(
        r"(?:对|向|陪着|看着|望着|见到|再见|遇到|看见|望见|碰到)(?:了)?"
        r"([\u4e00-\u9fff]{2,4})"
    ),
    re.compile(r"(?:名叫|叫|名为)([\u4e00-\u9fff]{2,4})"),
    re.compile(r"([\u4e00-\u9fff]{2,4})(?:说道|问道|笑道|答道|开口|点头)"),
    re.compile(
        r"(?:公主|皇后|皇女|女皇|圣女|神女|师尊|道侣|侍女|侍妾|夫人|表妹|秘书|助理|舰灵)"
        r"([\u4e00-\u9fff]{2,4})"
    ),
)
HEADING_NAME_PATTERNS = (
    re.compile(r"^第[0-9零一二三四五六七八九十百千两]+[章节卷回幕篇]\s*([\u4e00-\u9fff]{2,4})$"),
    re.compile(
        r"^第[0-9零一二三四五六七八九十百千两]+[章节卷回幕篇]\s*"
        r"(?:初见|再见|再会|重逢)([\u4e00-\u9fff]{2,4})$"
    ),
    re.compile(
        r"^第[0-9零一二三四五六七八九十百千两]+[章节卷回幕篇]\s*"
        r"([\u4e00-\u9fff]{2,4})(?:现身|登场)$"
    ),
)


@dataclass(slots=True)
class _EntityStats:
    name: str
    raw_hits: int = 0
    chapter_hits: int = 0
    early_hits: int = 0
    anchored_hits: int = 0
    female_hits: int = 0
    romance_hits: int = 0
    conflict_hits: int = 0
    title_hits: int = 0
    role_counts: Counter[str] = field(default_factory=Counter)
    snippets: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _PairStats:
    left: str
    right: str
    chapter_hits: int = 0
    romance_hits: int = 0
    conflict_hits: int = 0
    evidence: str | None = None


def _split_chapters(text: str) -> list[tuple[str, str]]:
    chapters: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if CHAPTER_HEADING_RE.match(stripped):
            if current_heading is not None:
                chapters.append((current_heading, "\n".join(current_lines).strip()))
            current_heading = stripped
            current_lines = []
            continue
        current_lines.append(stripped)

    if current_heading is not None:
        chapters.append((current_heading, "\n".join(current_lines).strip()))

    if chapters:
        return chapters

    paragraphs = [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]
    return [(f"段落{i}", paragraph) for i, paragraph in enumerate(paragraphs, start=1)]


def _looks_like_character_name(token: str) -> bool:
    if len(token) < 2 or len(token) > 4:
        return False
    if token in STOP_WORDS:
        return False
    if all(char in COMMON_FUNCTION_CHARS for char in token):
        return False
    if token.startswith(ORDINAL_PREFIXES):
        return False
    if token.endswith(GENERIC_SUFFIXES):
        return False
    if token[0] in {"这", "那", "其", "某", "对", "向", "把", "将", "与", "和"}:
        return False
    if token[-1] in {"说", "道", "问", "笑", "看", "听", "着", "了", "的"}:
        return False
    if any(char in token for char in ("说道", "问道", "看着", "听着")):
        return False
    return True


def _top_role(stats: _EntityStats) -> str | None:
    return stats.role_counts.most_common(1)[0][0] if stats.role_counts else None


def _heroine_score(stats: _EntityStats) -> int:
    role = _top_role(stats)
    role_bonus = 3 if role in FEMALE_ROLES else 0
    return stats.female_hits * 2 + stats.romance_hits * 3 + stats.title_hits * 2 + role_bonus


def _character_score(stats: _EntityStats) -> int:
    return (
        min(stats.raw_hits, 50)
        + stats.chapter_hits * 3
        + stats.anchored_hits * 4
        + stats.title_hits * 4
        + _heroine_score(stats)
        - stats.conflict_hits
    )


def _dedupe_names(items: list[_EntityStats]) -> list[_EntityStats]:
    deduped: list[_EntityStats] = []
    ranked = sorted(
        items,
        key=lambda value: (_character_score(value), len(value.name)),
        reverse=True,
    )
    for item in ranked:
        if any(item.name in existing.name or existing.name in item.name for existing in deduped):
            continue
        deduped.append(item)
    return deduped


def _iter_contexts(text: str, name: str, window: int = 20) -> list[str]:
    contexts: list[str] = []
    start = 0
    pattern = re.escape(name)
    while True:
        match = re.search(pattern, text[start:])
        if match is None:
            break
        index = start + match.start()
        left = max(0, index - window)
        right = min(len(text), index + len(name) + window)
        contexts.append(text[left:right])
        start = index + len(name)
        if len(contexts) >= 4:
            break
    return contexts


def _pick_role(text: str) -> str | None:
    for role in ROLE_KEYWORDS:
        if role in text:
            return role
    return None


def _is_anchored(name: str, context: str) -> bool:
    return any(f"{prefix}{name}" in context for prefix in ANCHOR_PREFIXES) or any(
        f"{name}{suffix}" in context for suffix in ANCHOR_SUFFIXES
    )


def _clean_snippet(text: str, limit: int = 60) -> str:
    compact = re.sub(r"\s+", "", text)
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _normalize_candidate(candidate: str) -> str:
    normalized = candidate.lstrip("了又再")
    for role in sorted(ROLE_KEYWORDS, key=len, reverse=True):
        if normalized.startswith(role) and len(normalized) > len(role):
            normalized = normalized[len(role) :]
            break
    return normalized


def _heading_names(heading: str) -> list[str]:
    names: list[str] = []
    for pattern in HEADING_NAME_PATTERNS:
        match = pattern.search(heading)
        if match is None:
            continue
        candidate = _normalize_candidate(match.group(1))
        if _looks_like_character_name(candidate):
            names.append(candidate)
    return names


def _extract_anchor_names(text: str) -> list[str]:
    names: list[str] = []
    for pattern in NAME_ANCHOR_PATTERNS:
        for match in pattern.finditer(text):
            candidate = _normalize_candidate(match.group(1))
            if _looks_like_character_name(candidate):
                names.append(candidate)
    return names


def _collect_candidate_stats(
    text: str, max_seeds: int = 160
) -> tuple[list[tuple[str, str]], dict[str, _EntityStats]]:
    chapters = _split_chapters(text)
    anchor_counter: Counter[str] = Counter()
    for heading, content in chapters:
        for name in _heading_names(heading):
            anchor_counter[name] += 2
        for sentence in SENTENCE_SPLIT_RE.split(content):
            for name in _extract_anchor_names(sentence):
                anchor_counter[name] += 1

    seed_names = [name for name, _ in anchor_counter.most_common(max_seeds)]
    stats_map = {name: _EntityStats(name=name) for name in seed_names}
    early_limit = max(30, len(chapters) // 8)

    for index, (heading, content) in enumerate(chapters, start=1):
        chapter_text = f"{heading}\n{content}"
        present = [name for name in seed_names if name in chapter_text]
        if not present:
            continue

        for name in present:
            stats = stats_map[name]
            occurrences = chapter_text.count(name)
            stats.raw_hits += occurrences
            stats.chapter_hits += 1
            if index <= early_limit:
                stats.early_hits += occurrences
            if name in heading:
                stats.title_hits += 1

            for context in _iter_contexts(chapter_text, name):
                if _is_anchored(name, context) or name in heading:
                    stats.anchored_hits += 1
                female_hits = sum(1 for hint in FEMALE_HINTS if hint in context)
                romance_hits = sum(1 for hint in ROMANCE_HINTS if hint in context)
                conflict_hits = sum(1 for hint in CONFLICT_HINTS if hint in context)
                stats.female_hits += female_hits
                stats.romance_hits += romance_hits
                stats.conflict_hits += conflict_hits

                role = _pick_role(context)
                if role:
                    stats.role_counts[role] += 1

                if (female_hits or romance_hits or role) and len(stats.snippets) < 3:
                    snippet = _clean_snippet(context)
                    if snippet not in stats.snippets:
                        stats.snippets.append(snippet)

    filtered = [
        item
        for item in stats_map.values()
        if (
            item.chapter_hits >= 1
            and (
                item.anchored_hits > 0
                or item.title_hits > 0
                or _heroine_score(item) >= 4
            )
            and _character_score(item) >= 10
        )
    ]
    return chapters, {item.name: item for item in _dedupe_names(filtered)}


def _pick_protagonist(stats_map: dict[str, _EntityStats]) -> str:
    if not stats_map:
        return "主角待复核"

    def protagonist_score(item: _EntityStats) -> tuple[int, int, int]:
        return (
            item.early_hits * 4
            + item.chapter_hits * 3
            + item.anchored_hits * 4
            - item.female_hits * 2,
            item.raw_hits,
            len(item.name),
        )

    return max(stats_map.values(), key=protagonist_score).name


def _pick_selected_names(
    stats_map: dict[str, _EntityStats], protagonist: str, max_nodes: int
) -> tuple[list[str], list[str], int]:
    protagonist_stats = stats_map.get(protagonist)
    heroine_candidates = [
        item
        for item in stats_map.values()
        if item.name != protagonist and _heroine_score(item) >= 4
    ]
    heroine_candidates.sort(
        key=lambda item: (_heroine_score(item), item.chapter_hits, item.raw_hits, len(item.name)),
        reverse=True,
    )

    selected = [protagonist] if protagonist_stats else []
    selected.extend(item.name for item in heroine_candidates[: max_nodes - 1])
    if len(selected) < max_nodes:
        others = sorted(
            (item for item in stats_map.values() if item.name not in selected),
            key=lambda item: (_character_score(item), item.chapter_hits, item.raw_hits),
            reverse=True,
        )
        selected.extend(item.name for item in others[: max_nodes - len(selected)])

    heroine_names = [item.name for item in heroine_candidates]
    heroine_pool_estimate = max(len(heroine_names), len(heroine_names[:8]) * 4)
    return selected[:max_nodes], heroine_names[:8], heroine_pool_estimate


def _pair_evidence(text: str, left: str, right: str) -> str | None:
    for sentence in SENTENCE_SPLIT_RE.split(text):
        if left in sentence and right in sentence:
            return _clean_snippet(sentence)
    return None


def build_lightweight_graph(text: str, max_nodes: int = 14) -> LightweightGraph:
    chapters, stats_map = _collect_candidate_stats(text)
    if not stats_map:
        return LightweightGraph(
            metadata={
                "method": "mirofish-style-chunk-graph",
                "chunk_count": len(chapters),
                "protagonist": None,
                "heroine_candidates": [],
                "core_characters": [],
                "relationship_highlights": [],
                "heroine_pool_estimate": 0,
            }
        )

    protagonist = _pick_protagonist(stats_map)
    selected_names, heroine_names, heroine_pool_estimate = _pick_selected_names(
        stats_map, protagonist, max_nodes=max_nodes
    )
    selected_stats = {name: stats_map[name] for name in selected_names if name in stats_map}
    heroine_set = set(heroine_names)

    pair_stats: dict[tuple[str, str], _PairStats] = defaultdict(lambda: _PairStats("", ""))
    for heading, content in chapters:
        chapter_text = f"{heading}\n{content}"
        present = [name for name in selected_names if name in chapter_text]
        if len(present) < 2:
            continue

        chapter_romance = sum(1 for hint in ROMANCE_HINTS if hint in chapter_text)
        chapter_conflict = sum(1 for hint in CONFLICT_HINTS if hint in chapter_text)

        for index, left in enumerate(present):
            for right in present[index + 1 :]:
                key = tuple(sorted((left, right)))
                current = pair_stats[key]
                if not current.left:
                    current.left, current.right = key
                current.chapter_hits += 1

                if protagonist in key:
                    other = right if left == protagonist else left
                    if other in heroine_set:
                        current.romance_hits += max(chapter_romance, 1)
                current.conflict_hits += chapter_conflict

                if current.evidence is None:
                    current.evidence = _pair_evidence(chapter_text, left, right)

    nodes = []
    for index, name in enumerate(selected_names, start=1):
        stats = selected_stats[name]
        role = None if name == protagonist else _top_role(stats)
        if name == protagonist:
            category = "主角"
        elif name in heroine_set:
            category = "女主候选"
        elif _heroine_score(stats) >= 4:
            category = "女性角色"
        else:
            category = "核心角色"

        tags: list[str] = []
        if _heroine_score(stats) >= 6:
            tags.append("高相关")
        if stats.title_hits > 0:
            tags.append("章节标题命中")
        if stats.anchored_hits > 0:
            tags.append("实体锚定")

        nodes.append(
            GraphNode(
                id=f"n{index}",
                label=name,
                category=category,
                weight=_character_score(stats),
                chapter_hits=stats.chapter_hits,
                role=role,
                evidence=stats.snippets[0] if stats.snippets else None,
                tags=tags,
            )
        )

    id_map = {node.label: node.id for node in nodes}
    edges = []
    for key, value in sorted(
        pair_stats.items(),
        key=lambda item: (
            item[1].chapter_hits + item[1].romance_hits * 2 + item[1].conflict_hits,
            item[1].romance_hits,
            item[1].chapter_hits,
        ),
        reverse=True,
    ):
        if value.chapter_hits < 2:
            continue
        if protagonist in key and any(name in heroine_set for name in key):
            relation = "后宫候选"
        elif value.conflict_hits > value.chapter_hits:
            relation = "冲突"
        else:
            relation = "同场互动"

        edges.append(
            GraphEdge(
                source=id_map[value.left],
                target=id_map[value.right],
                relation=relation,
                weight=value.chapter_hits + value.romance_hits * 2 + value.conflict_hits,
                chapter_hits=value.chapter_hits,
                evidence=value.evidence,
                tags=[
                    tag
                    for tag, enabled in (
                        ("暧昧", value.romance_hits > 0),
                        ("冲突", value.conflict_hits > 0),
                    )
                    if enabled
                ],
            )
        )

    core_characters = sorted(
        nodes,
        key=lambda item: (item.weight, item.chapter_hits),
        reverse=True,
    )[:6]
    heroine_candidates = [
        node
        for node in nodes
        if node.category in {"女主候选", "女性角色"} and node.label != protagonist
    ][:8]
    relationship_highlights = sorted(
        edges, key=lambda item: (item.weight, item.chapter_hits), reverse=True
    )[:8]
    reverse_id_map = {node_id: label for label, node_id in id_map.items()}

    return LightweightGraph(
        nodes=nodes,
        edges=edges,
        metadata={
            "method": "mirofish-style-chunk-graph",
            "chunk_count": len(chapters),
            "protagonist": protagonist,
            "heroine_pool_estimate": heroine_pool_estimate,
            "heroine_candidates": [
                {
                    "name": node.label,
                    "category": node.category,
                    "role": node.role,
                    "chapter_hits": node.chapter_hits,
                    "score": node.weight,
                    "evidence": node.evidence,
                }
                for node in heroine_candidates
            ],
            "core_characters": [
                {
                    "name": node.label,
                    "category": node.category,
                    "role": node.role,
                    "chapter_hits": node.chapter_hits,
                    "score": node.weight,
                    "evidence": node.evidence,
                }
                for node in core_characters
            ],
            "relationship_highlights": [
                {
                    "source": reverse_id_map.get(edge.source, edge.source),
                    "target": reverse_id_map.get(edge.target, edge.target),
                    "relation": edge.relation,
                    "chapter_hits": edge.chapter_hits,
                    "weight": edge.weight,
                    "evidence": edge.evidence,
                }
                for edge in relationship_highlights
            ],
        },
    )


def summarize_graph(graph: LightweightGraph) -> str:
    if not graph.nodes:
        return "未抽取到稳定角色图谱，建议缩小到单段正文后重试。"

    metadata = graph.metadata or {}
    protagonist = metadata.get("protagonist")
    heroines = metadata.get("heroine_candidates") or []
    relationships = metadata.get("relationship_highlights") or []
    method = metadata.get("method")

    if protagonist and method == "mirofish-style-chunk-graph":
        heroine_text = "、".join(item["name"] for item in heroines[:4]) or "女主候选待复核"
        relation_text = "；".join(
            f"{item['source']}->{item['target']}({item['relation']}, 共现{item['chapter_hits']}章)"
            for item in relationships[:3]
        )
        if not relation_text:
            relation_text = "暂未形成稳定高频关系边。"
        return (
            f"参考 MiroFish 的分块聚合方式，以 {protagonist} 为核心抽出角色关系图谱；"
            f"高相关女主候选包括 {heroine_text}。核心关系：{relation_text}"
        )

    label_map = {node.id: node.label for node in graph.nodes}
    core_nodes = sorted(graph.nodes, key=lambda node: node.weight, reverse=True)[:5]
    core_text = "、".join(f"{node.label}(出现{node.weight}次)" for node in core_nodes)

    if not graph.edges:
        return f"核心角色：{core_text}。角色共现关系较弱，暂未形成稳定互动边。"

    core_edges = sorted(graph.edges, key=lambda edge: edge.weight, reverse=True)[:5]
    edge_text = "；".join(
        (
            f"{label_map.get(edge.source, edge.source)}"
            f"->{label_map.get(edge.target, edge.target)}(共现{edge.weight}次)"
        )
        for edge in core_edges
    )
    return f"核心角色：{core_text}。高频互动边：{edge_text}。"
