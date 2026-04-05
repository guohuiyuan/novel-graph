from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

import jieba
import jieba.posseg as pseg

from novel_graph.analysis.keywords import top_candidate_names
from novel_graph.domain.models import NovelInput

CHAPTER_HEADING_RE = re.compile(
    r"^第[0-9零一二三四五六七八九十百千两]+章(?:\s+.*)?$"
)
TITLE_NAME_RE = re.compile(
    r"^第[0-9零一二三四五六七八九十百千两]+章\s+([\u4e00-\u9fff]{2,6})$"
)
NAME_RE = re.compile(r"^[\u4e00-\u9fff]{2,6}$")
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]")

PERSON_STOP_WORDS = {
    "说着",
    "地道",
    "当然",
    "之后",
    "下来",
    "起来",
    "什么",
    "好吧",
    "过来",
    "的话",
    "如果不是",
    "东西",
    "是的",
    "一下",
    "一笑",
    "没错",
    "罢了",
    "呵呵",
    "等等",
    "问题",
    "事情",
    "可以",
    "人物",
    "存在",
    "世界",
    "资源",
    "修为",
    "能力",
    "时间",
    "好的",
    "而言",
    "不少",
    "了吧",
    "问道",
    "问着",
    "片刻之后",
    "须臾之后",
    "的事情",
    "了口气",
    "多了",
    "出来",
    "所以",
    "而已",
    "不错",
    "当然了",
    "事情不出",
    "完全可以",
    "人类文明",
    "文明阵营",
    "世界本源",
    "太虚星空",
    "至高星尊",
    "极星联盟",
    "星舰中枢",
    "时空星舰",
    "舰娘羽澶",
    "秦烽说着",
    "秦烽点点",
    "秦烽微微",
    "秦烽心里",
    "所以秦烽",
    "文明",
    "高阶",
    "明白",
    "太虚",
    "灵宝",
    "智慧",
    "元帅",
    "罗金仙",
    "星蒙",
    "星尊",
    "鸿蒙",
    "金仙",
    "宫殿",
    "子嗣",
    "诸侯",
    "令人",
    "气数",
    "浮屠",
    "白银",
    "权限提升",
    "楚王",
    "王总管",
    "劳斯莱斯",
    "采取任何",
    "双修",
    "小女儿",
    "殷勤",
    "陈设",
    "山珍海味",
    "丽颜",
}

ROLE_STOP_WORDS = {
    "王妃",
    "皇后",
    "王后",
    "公主",
    "圣女",
    "神女",
    "师尊",
    "掌教",
    "太后",
    "小姐",
    "丫鬟",
    "助理",
    "保镖",
    "夫人",
    "女儿",
    "侍女",
    "侍妾",
    "太子妃",
    "元配",
}

FEMALE_CONTEXT = (
    "她",
    "少女",
    "女子",
    "女人",
    "美女",
    "美妇",
    "佳人",
    "公主",
    "皇后",
    "皇女",
    "女皇",
    "圣女",
    "神女",
    "表姐",
    "闺蜜",
    "师尊",
    "侍女",
    "侍妾",
    "夫人",
    "小姐",
    "娘娘",
    "丫鬟",
    "女儿",
    "母后",
)

MALE_CONTEXT = (
    "男子",
    "男人",
    "少年",
    "青年",
    "公子",
    "殿下",
    "皇帝",
    "太子",
    "王爷",
    "少主",
    "师兄",
    "师弟",
    "将军",
    "长老",
    "岳父",
    "哥哥",
    "父亲",
    "义父",
    "首辅",
    "男性",
    "总指挥",
    "侯爵",
    "代理掌教",
)

CONFIRMED_SIGNALS = (
    "女人",
    "妻子",
    "女友",
    "皇后",
    "王妃",
    "妃子",
    "妃",
    "道侣",
    "双修",
    "侍寝",
    "侍妾",
    "侍女",
    "房中",
    "圆房",
    "云雨",
    "宠幸",
    "献身",
    "收入房中",
    "共侍",
    "喜欢上他",
    "怀孕",
    "小腹",
    "生下",
    "女儿",
)

PROBABLE_SIGNALS = (
    "喜欢",
    "爱意",
    "倾心",
    "心动",
    "暗恋",
    "表白",
    "夜袭",
    "亲吻",
    "婚约",
    "联姻",
    "驸马",
    "示好",
    "投怀送抱",
    "暧昧",
    "心仪",
    "痴迷",
    "追求",
)

ROLE_KEYWORDS = (
    "远房表姐",
    "长公主",
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
    "闺蜜",
    "表姐",
    "侍女",
    "侍妾",
    "夫人",
    "秘书",
    "助理",
    "保镖",
    "管家",
    "导师",
    "丫鬟",
    "掌教",
    "宗主",
    "宫主",
    "女儿",
)

FEMALE_ROLE_SET = {
    "远房表姐",
    "长公主",
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
    "闺蜜",
    "表姐",
    "侍女",
    "侍妾",
    "夫人",
    "秘书",
    "助理",
    "保镖",
    "管家",
    "导师",
    "丫鬟",
    "掌教",
    "宗主",
    "宫主",
    "女儿",
}

HARD_CONFIRM_ROLES = {
    "舰灵",
    "世界意志",
    "位面意志",
    "皇后",
    "王妃",
    "道侣",
    "侍妾",
    "侍女",
}

TRAIT_KEYWORDS = (
    "高冷",
    "清冷",
    "妩媚",
    "温柔",
    "强势",
    "活泼",
    "聪慧",
    "果断",
    "精明",
    "端庄",
    "成熟",
    "御姐",
    "娇憨",
    "可爱",
    "高贵",
    "圣洁",
    "妖娆",
    "冷艳",
    "忠诚",
    "听话",
    "顺从",
    "知性",
    "腹黑",
    "霸道",
    "痴情",
    "空灵",
    "神圣",
    "大气",
)

ARC_RULES = (
    ("古代争霸", ("赵元谨", "大齐", "大楚", "国师")),
    ("末世废土", ("末世", "基地", "昆仑之巅", "废墟", "辐射")),
    ("西幻封神", ("星濛", "魔法", "神国", "主神", "精灵")),
    ("修真仙侠", ("太皓星宫", "仙门", "上界", "飞升", "道侣")),
    ("星海战争", ("极星联盟", "太虚星空", "至高星尊", "帝国", "星海宇宙")),
)

SPICY_TERMS = ("开车", "双修", "云雨", "侍寝", "房中", "献身", "侍奉", "圆房")
CAOZEI_TERMS = ("表姐", "母后", "母亲", "姑姑", "夫人", "皇后", "美妇", "人妻", "女儿")
THUNDER_TERMS = {
    "绿帽": ("绿帽", "牛头人", "被绿"),
    "死女": ("女主死", "红颜陨落", "香消玉殒"),
    "送女": ("送女", "拱手让人", "送给别人"),
    "背叛": ("背叛", "叛变", "转投他人"),
    "wrq": ("万人骑", "wrq"),
    "龟作": ("龟作", "知雷写雷"),
}


@dataclass(slots=True)
class Chapter:
    index: int
    heading: str
    content: str


@dataclass(slots=True)
class CharacterAccumulator:
    name: str
    score: int = 0
    mention_count: int = 0
    female_hits: int = 0
    male_hits: int = 0
    confirmed_hits: int = 0
    probable_hits: int = 0
    role_counts: Counter[str] = field(default_factory=Counter)
    trait_counts: Counter[str] = field(default_factory=Counter)
    snippets: list[str] = field(default_factory=list)
    chapter_hints: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CharacterDigest:
    name: str
    role: str | None
    traits: list[str]
    summary: str
    evidence: str
    chapter_hint: str
    status: str
    score: int


@dataclass(slots=True)
class BookProfile:
    title: str
    author: str | None
    word_count: int
    word_count_display: str
    status: str
    platform: str
    time_label: str
    protagonist: str
    synopsis: str
    headline: str
    tags: list[str]
    grades: dict[str, str]
    confirmed_heroines: list[CharacterDigest]
    probable_heroines: list[CharacterDigest]
    heroine_pool_size: int
    heroine_pool_label: str
    selling_points: list[str]
    commentary: list[str]
    thunder_lines: list[str]
    depress_lines: list[str]
    reader_fit: list[str]
    reader_caution: list[str]
    closing: str
    arc_summary: list[str]


def _strip_toc(raw_text: str) -> str:
    lines = raw_text.splitlines()
    if len(lines) < 3:
        return raw_text

    first_heading = lines[1].strip()
    if not first_heading or not CHAPTER_HEADING_RE.match(first_heading):
        return raw_text

    first_pos = raw_text.find(first_heading)
    second_pos = raw_text.find(first_heading, first_pos + len(first_heading))
    if second_pos == -1:
        return raw_text

    return raw_text[second_pos:].strip()


def _split_chapters(text: str) -> list[Chapter]:
    chapters: list[Chapter] = []
    current_heading: str | None = None
    current_lines: list[str] = []

    for line in text.splitlines():
        stripped = line.strip()
        if CHAPTER_HEADING_RE.match(stripped):
            if current_heading is not None:
                content = "\n".join(current_lines).strip()
                chapters.append(
                    Chapter(index=len(chapters) + 1, heading=current_heading, content=content)
                )
            current_heading = stripped
            current_lines = []
            continue

        current_lines.append(stripped)

    if current_heading is not None:
        content = "\n".join(current_lines).strip()
        chapters.append(Chapter(index=len(chapters) + 1, heading=current_heading, content=content))

    return chapters


def _looks_like_name(token: str) -> bool:
    if not NAME_RE.fullmatch(token):
        return False
    if token in PERSON_STOP_WORDS:
        return False
    if token in ROLE_STOP_WORDS:
        return False
    if token.endswith(("世界", "帝国", "联盟", "王朝", "星宫", "星舰", "星空")):
        return False
    if token.startswith(("第一", "第二", "第三", "第四", "第五")):
        return False
    return True


def _extract_person_names(text: str) -> list[str]:
    names: list[str] = []
    for word, flag in pseg.cut(text):
        token = str(word).strip()
        if not token:
            continue
        if flag.startswith("nr") and _looks_like_name(token):
            names.append(token)
    return names


def _normalize_name(name: str, evidence: str) -> str:
    best = name
    for token in re.findall(r"[\u4e00-\u9fff]{2,8}", evidence):
        if name not in token:
            continue
        candidate = re.sub(r"^[一二三四五六七八九十]+皇女", "", token)
        candidate = re.sub(r"^[一二三四五六七八九十]+公主", "", candidate)
        for prefix in sorted(ROLE_KEYWORDS, key=len, reverse=True):
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix) :]
        for suffix in ("冷笑", "出言", "出", "和诸位", "已经不"):
            if candidate.endswith(suffix):
                candidate = candidate[: -len(suffix)]
        if _looks_like_name(candidate) and len(candidate) > len(best):
            best = candidate
    return best


def _is_name_anchored(name: str, evidence: str) -> bool:
    prefixes = (
        "名叫",
        "叫",
        "是",
        "少女",
        "美女",
        "公主",
        "皇后",
        "女皇",
        "皇女",
        "圣女",
        "表姐",
        "夫人",
        "师尊",
        "导师",
        "侍女",
        "五皇女",
        "长公主",
    )
    suffixes = ("说道", "问道", "问着", "笑道", "温言道", "出言道", "道")
    if any(f"{prefix}{name}" in evidence for prefix in prefixes):
        return True
    if any(f"{name}{suffix}" in evidence for suffix in suffixes):
        return True
    return any(token in evidence for token in (f"{name}，", f"{name}。", f"{name}："))


def _title_name(heading: str) -> str | None:
    match = TITLE_NAME_RE.match(heading)
    if not match:
        return None

    candidate = match.group(1).strip()
    if not _looks_like_name(candidate):
        return None
    return candidate


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?])|\n+", text)
    return [part.strip() for part in parts if part.strip()]


def _pick_role(text: str) -> str | None:
    for role in ROLE_KEYWORDS:
        if role in text:
            return role
    return None


def _pick_traits(text: str) -> list[str]:
    traits = [trait for trait in TRAIT_KEYWORDS if trait in text]
    return traits[:3]


def _clean_snippet(text: str, limit: int = 68) -> str:
    compact = re.sub(r"\s+", "", text)
    compact = compact.replace("“", "").replace("”", "")
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}…"


def _guess_protagonist(chapters: list[Chapter]) -> str:
    full_text = "\n".join(f"{chapter.heading}\n{chapter.content}" for chapter in chapters)
    sample_text = "\n".join(
        f"{chapter.heading}\n{chapter.content[:1200]}" for chapter in chapters[:160]
    )
    candidate_names = set(_extract_person_names(sample_text))
    candidate_names.update(top_candidate_names(full_text, limit=48))

    if not candidate_names:
        return "主角待复核"

    scored = []
    for name in candidate_names:
        if not _looks_like_name(name):
            continue
        score = full_text.count(name) + sample_text.count(name) * 2
        if score <= 0:
            continue
        scored.append((score, name))

    if not scored:
        return "主角待复核"

    scored.sort(reverse=True)
    return scored[0][1]


def _contexts_around_name(text: str, name: str, window: int = 20) -> list[str]:
    contexts: list[str] = []
    start = 0
    while True:
        index = text.find(name, start)
        if index == -1:
            break
        left = max(0, index - window)
        right = min(len(text), index + len(name) + window)
        contexts.append(text[left:right])
        start = index + len(name)
    return contexts


def _collect_character_candidates(
    chapters: list[Chapter], protagonist: str
) -> list[CharacterAccumulator]:
    candidates: dict[str, CharacterAccumulator] = {}

    for chapter in chapters:
        chapter_text = f"{chapter.heading}\n{chapter.content}"
        if protagonist not in chapter_text:
            continue

        names = set(_extract_person_names(chapter_text))
        title_name = _title_name(chapter.heading)
        if title_name:
            names.add(title_name)

        if not names:
            continue

        sentences = _split_sentences(chapter.content)
        for name in names:
            if name == protagonist or not _looks_like_name(name):
                continue

            related_sentences: list[str] = []
            for sentence in sentences:
                if name not in sentence:
                    continue
                signal_terms = FEMALE_CONTEXT + CONFIRMED_SIGNALS + PROBABLE_SIGNALS
                if any(term in sentence for term in signal_terms):
                    related_sentences.append(sentence)
                    continue
                if protagonist in sentence:
                    related_sentences.append(sentence)

            if not related_sentences and title_name == name:
                related_sentences = sentences[:3]

            if not related_sentences:
                continue

            evidence = " ".join(related_sentences[:2])
            normalized_name = _normalize_name(name, evidence)
            if normalized_name == protagonist or not _looks_like_name(normalized_name):
                continue
            local_context = " ".join(
                context
                for sentence in related_sentences[:2]
                for context in _contexts_around_name(sentence, name)
            )
            role = _pick_role(local_context)
            female_hits = sum(1 for token in FEMALE_CONTEXT if token in local_context)
            male_hits = sum(1 for token in MALE_CONTEXT if token in local_context)
            confirmed_hits = sum(1 for token in CONFIRMED_SIGNALS if token in local_context)
            probable_hits = sum(1 for token in PROBABLE_SIGNALS if token in local_context)

            if (
                female_hits == 0
                and confirmed_hits == 0
                and probable_hits == 0
                and title_name != name
            ):
                continue

            if role in FEMALE_ROLE_SET:
                female_hits += 2
            if title_name == name:
                female_hits += 1
            anchored = _is_name_anchored(normalized_name, evidence)
            if not anchored and title_name != name and confirmed_hits == 0 and probable_hits == 0:
                continue

            score = (
                female_hits * 2
                + confirmed_hits * 3
                + probable_hits * 2
                + min(len(related_sentences), 3)
                - male_hits * 2
            )
            if title_name == name:
                score += 2

            if score <= 0:
                continue

            accumulator = candidates.setdefault(
                normalized_name, CharacterAccumulator(name=normalized_name)
            )
            accumulator.score += score
            accumulator.mention_count += 1
            accumulator.female_hits += female_hits
            accumulator.male_hits += male_hits
            accumulator.confirmed_hits += confirmed_hits
            accumulator.probable_hits += probable_hits
            if role:
                accumulator.role_counts[role] += 1
            for trait in _pick_traits(local_context or evidence):
                accumulator.trait_counts[trait] += 1
            snippet = _clean_snippet(evidence)
            if snippet and snippet not in accumulator.snippets and len(accumulator.snippets) < 3:
                accumulator.snippets.append(snippet)
            if (
                chapter.heading not in accumulator.chapter_hints
                and len(accumulator.chapter_hints) < 3
            ):
                accumulator.chapter_hints.append(chapter.heading)

    return list(candidates.values())


def _finalize_characters(
    candidates: list[CharacterAccumulator],
) -> tuple[list[CharacterDigest], list[CharacterDigest], int]:
    confirmed: list[CharacterDigest] = []
    probable: list[CharacterDigest] = []
    pool_size = 0

    ranked = sorted(
        candidates,
        key=lambda item: (
            item.confirmed_hits,
            item.probable_hits,
            item.female_hits,
            item.score,
            item.mention_count,
        ),
        reverse=True,
    )

    for item in ranked:
        if item.score < 4:
            continue
        if (
            item.female_hits <= item.male_hits
            and item.confirmed_hits == 0
            and item.probable_hits == 0
        ):
            continue

        role = item.role_counts.most_common(1)[0][0] if item.role_counts else None
        chapter_hint = item.chapter_hints[0] if item.chapter_hints else "章节待复核"
        evidence = item.snippets[0] if item.snippets else "正文证据待补"
        if role == "女儿":
            continue
        if any(token in evidence for token in ("爸爸", "小公主", "继承人", "生下了长子和女儿")):
            continue

        status: str | None = None
        if (
            item.confirmed_hits > 0
            or role in HARD_CONFIRM_ROLES
            or (item.confirmed_hits == 0 and item.probable_hits >= 2 and item.score >= 8)
        ):
            status = "已确认女主"
        elif item.probable_hits > 0 or (role in FEMALE_ROLE_SET and item.score >= 6):
            status = "高概率女主"

        if status is None:
            continue

        pool_size += 1
        digest = CharacterDigest(
            name=item.name,
            role=role,
            traits=[name for name, _ in item.trait_counts.most_common(3)],
            summary=evidence,
            evidence=evidence,
            chapter_hint=chapter_hint,
            status=status,
            score=item.score,
        )
        if status == "已确认女主":
            confirmed.append(digest)
        else:
            probable.append(digest)

    return confirmed[:12], probable[:10], pool_size


def _count_word_chars(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _format_word_count(word_count: int) -> str:
    if word_count >= 10000:
        return f"约{round(word_count / 10000):.0f}万字"
    return f"{word_count}字"


def _infer_book_status(chapters: list[Chapter]) -> str:
    if chapters and any(token in chapters[-1].heading for token in ("终章", "大结局", "完本")):
        return "完结"
    return "待复核"


def _infer_time_label(novel_input: NovelInput) -> str:
    if novel_input.published_at:
        year_match = re.search(r"(20\d{2})", novel_input.published_at)
        if year_match and year_match.group(1) not in {"2025", "2026"}:
            return year_match.group(1)
    return "待复核（EPUB 仅含导出日期或未标注）"


def _infer_arcs(text: str) -> list[str]:
    arcs: list[str] = []
    for label, keywords in ARC_RULES:
        if any(keyword in text for keyword in keywords):
            arcs.append(label)
    return arcs or ["跨界升级"]


def _infer_tags(text: str, heroine_pool_size: int, arcs: list[str]) -> list[str]:
    tags: list[str] = []
    if heroine_pool_size >= 8 or "后宫" in text:
        tags.append("后宫")
    if "时空" in text or "诸天" in text or len(arcs) >= 3:
        tags.append("无限")
    if any(term in text for term in ("星海", "战舰", "帝国", "联盟")):
        tags.append("星际")
    if any(term in text for term in ("双修", "献身", "侍寝", "房中")):
        tags.append("车速快")
    if sum(text.count(term) for term in CAOZEI_TERMS) >= 12:
        tags.append("曹贼")
    if heroine_pool_size >= 15:
        tags.append("推土机")
    return tags or ["待复核"]


def _headline_count(heroine_pool_size: int) -> str:
    if heroine_pool_size >= 60:
        return "60+"
    if heroine_pool_size >= 40:
        return "40+"
    if heroine_pool_size >= 20:
        return "20+"
    if heroine_pool_size >= 10:
        return "10+"
    return "多"


def _grade_from_score(score: int) -> str:
    if score >= 10:
        return "S+"
    if score >= 9:
        return "S"
    if score >= 8:
        return "A+"
    if score >= 7:
        return "A"
    if score >= 6:
        return "A-"
    if score >= 5:
        return "B+"
    if score >= 4:
        return "B"
    return "C"


def _build_grades(
    arcs: list[str], heroine_pool_size: int, spicy_score: int, thunder_count: int
) -> dict[str, str]:
    plot_score = 6 + min(len(arcs), 3)
    prose_score = 6 if len(arcs) >= 4 else 5
    emotion_score = 5 + min(heroine_pool_size // 10, 2)
    vehicle_score = 8 + min(spicy_score // 60, 2)
    character_score = 5 + min(heroine_pool_size // 12, 3)
    novelty_score = 5 + min(len(arcs), 3)
    oppression = "C" if thunder_count == 0 else "B"
    overall_score = max(plot_score, emotion_score, vehicle_score, novelty_score) - 1

    return {
        "情节": _grade_from_score(plot_score),
        "文笔": _grade_from_score(prose_score),
        "感情": _grade_from_score(emotion_score),
        "车速": _grade_from_score(vehicle_score),
        "人物刻画": _grade_from_score(character_score),
        "新意": _grade_from_score(novelty_score),
        "压抑度": oppression,
        "总评": _grade_from_score(overall_score),
    }


def _build_synopsis(protagonist: str, arcs: list[str]) -> str:
    arc_tail = "、".join(arcs[:5])
    return (
        f"{protagonist}靠时空星舰起家，从古代资源倒卖一路滚成跨界霸主，"
        f"主线节奏基本就是“换世界、抢资源、扩势力、收高位女角”。"
        f"全书覆盖{arc_tail}几档地图，后期直接抬到星海终局与永恒超脱。"
    )


def _build_selling_points(
    heroine_pool_size: int, tags: list[str], arcs: list[str], spicy_score: int
) -> list[str]:
    points = [
        "诸天/无限框架下的超级推土机模板，地图推进很快，爽点切换频繁。",
        (
            f"女角池规模非常夸张，本地抽取规模至少在 {_headline_count(heroine_pool_size)} 这一档，"
            "公主、皇后、圣女、师尊、舰灵这类高位配置都不缺。"
        ),
        f"世界跨度大，至少覆盖 {'、'.join(arcs[:5])}，每换一界就换一批新资源与新后宫入口。",
    ]
    if spicy_score >= 180 or "车速快" in tags:
        points.append("亲密戏密度偏高，整体明显不是清水升级流。")
    if "曹贼" in tags:
        points.append("表姐、母女、姑姑、美妇一类年上/伦理边界元素浓，口味很冲。")
    return points[:5]


def _build_commentary(
    protagonist: str,
    heroine_pool_size: int,
    arcs: list[str],
    spicy_score: int,
    graph_summary: str | None = None,
) -> list[str]:
    lines = [
        "剧情方面：前中期靠资源差和位面切换撑爽感，古代起家、末世发育、西幻封神、修真飞升到星海统一，属于一路横推型长篇。",
        (
            f"男主方面：{protagonist}是标准利己型推土机男主，做事果断，"
            "基本不走扭捏路线，爽文读者会比较容易对上电波。"
        ),
        (
            "女主方面：数量是真正的核心卖点之一，"
            f"本地高相关名单已过 {_headline_count(heroine_pool_size)}，"
            "而且高位女性占比很高，属于不断升级后宫规格的写法。"
        ),
        (
            f"世界观方面：{' -> '.join(arcs[:5])} 这种跨图切换让新鲜感始终在线，"
            "但后期也会明显进入“升级-收女-开战”的循环。"
        ),
        (
            "车速方面：车门基本焊死。"
            if spicy_score >= 180
            else "车速方面：亲密戏存在感不低，但更偏快餐式推进。"
        ),
    ]
    if graph_summary:
        lines.append(f"图谱补充：{graph_summary}")
    return lines


def _build_thunder_lines(
    chapters: list[Chapter], protagonist: str, heroine_names: set[str]
) -> list[str]:
    findings: list[str] = []
    for label, keywords in THUNDER_TERMS.items():
        if label not in {"绿帽", "wrq"}:
            continue
        for chapter in chapters:
            chapter_text = f"{chapter.heading}\n{chapter.content}"
            if protagonist not in chapter_text:
                continue
            if not any(keyword in chapter_text for keyword in keywords):
                continue
            related_names = [name for name in heroine_names if name in chapter_text]
            if not related_names:
                continue
            findings.append(
                (
                    f"- [{label}] {chapter.heading} 出现风险关键词，涉及 {related_names[0]}，"
                    "需人工复核具体是否属于六雷。"
                )
            )
            break

    if findings:
        return findings

    return [
        (
            "- 暂未检出与已收/高概率女角直接绑定的六雷硬证据，"
            "整本更像一路横推的爽文后宫，低雷读者相对友好。"
        )
    ]


def _build_depress_lines(tags: list[str], heroine_pool_size: int) -> list[str]:
    lines = [
        "- [快餐感] 女角数量极大，很多关系推进偏“看对眼/形势到位/直接收”，细腻恋爱党容易觉得太快。",
        (
            "- [后期循环] 中后段地图越开越大，容易进入“升级-收女-打仗”的重复套路，"
            "追求精细主线的读者可能会疲劳。"
        ),
    ]
    if "曹贼" in tags:
        lines.append(
            "- [口味门槛] 表姐、母女、姑姑、美妇等元素密度高，"
            "不吃年上/伦理边界玩法的读者需要提前绕路。"
        )
    if heroine_pool_size >= 30:
        lines.append("- [记忆负担] 女角池非常大，后期名单容易记混，一些人物更偏标签化爽点位。")
    return lines[:4]


def _build_reader_fit(tags: list[str]) -> tuple[list[str], list[str]]:
    fit = [
        "喜欢诸天/无限框架下的推土机爽文。",
        "能接受高位女性密集入宫，重点看征服感、规模感和车速。",
        "愿意把它当成长篇量大管饱的后宫流水席来看。",
    ]
    caution = [
        "只想看一对一或慢热细腻恋爱线的读者。",
        "不接受年上、母女、表姐、美妇等曹贼口味的读者。",
        "对后期战力膨胀和套路重复非常敏感的读者。",
    ]
    if "车速快" not in tags:
        caution = caution[:2]
    return fit, caution


def build_book_profile(
    novel_input: NovelInput, graph_summary: str | None = None
) -> BookProfile:
    jieba.initialize()

    main_text = _strip_toc(novel_input.raw_text)
    chapters = _split_chapters(main_text)
    protagonist = _guess_protagonist(chapters)
    candidate_pool = _collect_character_candidates(chapters, protagonist)
    confirmed, probable, heroine_pool_size = _finalize_characters(candidate_pool)
    word_count = _count_word_chars(main_text)
    status = _infer_book_status(chapters)
    time_label = _infer_time_label(novel_input)
    platform = novel_input.publisher or "待复核"
    arcs = _infer_arcs(main_text)
    tags = _infer_tags(main_text, heroine_pool_size, arcs)
    spicy_score = sum(main_text.count(term) for term in SPICY_TERMS)
    thunder_lines = _build_thunder_lines(
        chapters, protagonist, {item.name for item in confirmed + probable}
    )
    thunder_detected = 0 if thunder_lines[0].startswith("- 暂未") else len(thunder_lines)
    grades = _build_grades(arcs, heroine_pool_size, spicy_score, thunder_detected)
    word_count_display = _format_word_count(word_count)
    headline_tail: list[str] = []
    if "无限" in tags:
        headline_tail.append("无限后宫")
    else:
        headline_tail.append("诸天后宫")
    if "推土机" in tags:
        headline_tail.append("推土感强")
    if "曹贼" in tags:
        headline_tail.append("曹贼味重")

    headline = (
        f"{status if status == '完结' else '长篇'}粮草："
        f"{_headline_count(heroine_pool_size)}女主的{' '.join(headline_tail)} {word_count_display}"
    )
    selling_points = _build_selling_points(heroine_pool_size, tags, arcs, spicy_score)
    commentary = _build_commentary(
        protagonist, heroine_pool_size, arcs, spicy_score, graph_summary=graph_summary
    )
    depress_lines = _build_depress_lines(tags, heroine_pool_size)
    reader_fit, reader_caution = _build_reader_fit(tags)
    closing = (
        "如果你要的就是超长篇、全图横推、一路收高位女角的后宫爽文，这本基本就是对口粮草；"
        "如果你更在乎细腻恋爱和后期收束，那它的快餐感与重复度需要提前做好心理准备。"
    )

    return BookProfile(
        title=novel_input.title,
        author=novel_input.author,
        word_count=word_count,
        word_count_display=word_count_display,
        status=status,
        platform=platform,
        time_label=time_label,
        protagonist=protagonist,
        synopsis=_build_synopsis(protagonist, arcs),
        headline=headline,
        tags=tags,
        grades=grades,
        confirmed_heroines=confirmed,
        probable_heroines=probable,
        heroine_pool_size=heroine_pool_size,
        heroine_pool_label=f"{_headline_count(heroine_pool_size)}女主",
        selling_points=selling_points,
        commentary=commentary,
        thunder_lines=thunder_lines,
        depress_lines=depress_lines,
        reader_fit=reader_fit,
        reader_caution=reader_caution,
        closing=closing,
        arc_summary=arcs,
    )
