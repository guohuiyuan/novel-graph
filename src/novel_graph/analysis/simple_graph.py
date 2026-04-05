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
NAME_RE = re.compile(r"[\u4e00-\u9fff]{2,6}")
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
    "礼物",
    "邀请",
    "情报",
    "重宝",
    "开战",
    "狩猎",
    "重伤",
    "偷袭",
    "幕后",
    "战利品",
    "采购",
    "潜入",
    "启程",
    "胜出",
    "血战",
    "抹杀",
    "全军覆没",
    "损失惨重",
    "命星境",
    "昆仑之巅",
    "众神之启",
    "星舰本体",
    "印迦提尔",
    "渡幽星舟",
    "化身",
    "处理",
    "离开",
    "护卫",
    "至尊",
    "摇摇头",
    "叹了口气",
    "强大",
    "强者",
    "空间",
    "家伙",
    "周围",
    "高层",
    "空中",
    "方面",
    "时空",
    "容易",
    "简单",
    "宗门",
    "利益",
    "国家",
    "任务",
    "丰厚",
    "能量",
    "后面",
    "许多",
    "法则",
    "权柄",
    "平静",
    "高星尊",
    "相提并论",
    "计划",
    "时代",
    "万年",
    "左右",
    "后纪雨樱",
    "国度",
    "成就",
    "蒙先天至",
    "元罗界天",
    "时空巡狩",
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
    "名叫",
    "名为",
    "叫",
    "公主",
    "皇后",
    "皇女",
    "长公主",
    "女皇",
    "圣女",
    "神女",
    "师尊",
    "道侣",
    "侍女",
    "侍妾",
    "夫人",
    "表姐",
    "表妹",
    "秘书",
    "助理",
    "保镖",
    "导师",
    "掌教",
    "宫主",
    "宗主",
    "舰灵",
)
ANCHOR_SUFFIXES = (
    "说道",
    "问道",
    "笑道",
    "答道",
    "点头",
    "开口",
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
    "长公主",
    "女皇",
    "圣女",
    "神女",
    "师尊",
    "道侣",
    "表姐",
    "侍女",
    "侍妾",
    "夫人",
    "表妹",
    "闺蜜",
    "闺蜜",
    "秘书",
    "助理",
    "保镖",
    "管家",
    "导师",
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
    "远房表姐",
    "舰灵",
    "世界意志",
    "位面意志",
    "女皇",
    "皇后",
    "皇女",
    "长公主",
    "公主",
    "王妃",
    "圣女",
    "神女",
    "师尊",
    "道侣",
    "表姐",
    "闺蜜",
    "侍女",
    "侍妾",
    "夫人",
    "表妹",
    "秘书",
    "助理",
    "保镖",
    "管家",
    "导师",
    "掌教",
    "宫主",
    "宗主",
)
FEMALE_ROLES = {
    "远房表姐",
    "舰灵",
    "世界意志",
    "位面意志",
    "女皇",
    "皇后",
    "皇女",
    "长公主",
    "公主",
    "王妃",
    "圣女",
    "神女",
    "师尊",
    "道侣",
    "表姐",
    "闺蜜",
    "侍女",
    "侍妾",
    "夫人",
    "表妹",
    "秘书",
    "助理",
    "保镖",
    "管家",
    "导师",
    "掌教",
    "宫主",
    "宗主",
}

ROLE_PATTERN = "|".join(sorted(ROLE_KEYWORDS, key=len, reverse=True))

COMPOUND_SURNAMES = (
    "欧阳",
    "司马",
    "上官",
    "东方",
    "独孤",
    "南宫",
    "慕容",
    "令狐",
    "诸葛",
    "司徒",
    "司空",
    "夏侯",
    "尉迟",
    "公孙",
    "轩辕",
    "皇甫",
    "澹台",
    "宇文",
    "长孙",
    "太叔",
    "东郭",
    "南门",
    "呼延",
    "归海",
)
COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐"
    "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
    "和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁"
    "杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍"
    "虞万支柯管卢莫房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程邢"
    "滑裴陆荣翁荀羊惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷"
    "车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙叶幸司韶"
    "郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟"
    "谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏"
    "柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿弘匡国文寇广"
    "禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养"
    "鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公仉督岳帅缑亢况郈有琴归海晋"
    "楚闫法汝鄢涂钦缪干况那墨洛青"
)
NON_NAME_SUBSTRINGS = (
    "之启",
    "之巅",
    "本体",
    "惨重",
    "全军",
    "一眼",
    "开战",
    "重伤",
    "潜入",
    "启程",
)
NON_NAME_ENDINGS = {
    "开",
    "卫",
    "理",
    "身",
    "品",
    "物",
    "请",
    "报",
    "讯",
    "战",
    "伤",
    "宝",
    "程",
    "境",
    "营",
    "舟",
    "启",
    "头",
    "势",
    "局",
    "军",
    "谋",
}
TRAILING_NAME_NOISE = (
    "心动",
    "现身",
    "登场",
    "初见",
    "再见",
    "再会",
    "重逢",
)
WORLDLINE_RULES = (
    ("诸天常驻", ("舰灵", "星舰", "中枢", "穿梭时空", "位面穿梭")),
    ("主世界", ("主世界", "公司", "集团", "商业帝国", "助理", "秘书", "保镖", "表姐")),
    ("古代王朝", ("大齐", "大楚", "王朝", "国师", "王都", "王妃", "后宫", "公主", "皇后")),
    ("末世废土", ("末世", "基地", "昆仑之巅", "辐射", "废土", "佣兵", "城主", "异族")),
    ("星濛世界", ("星濛", "魔法", "主神", "神国", "精灵", "教廷", "神系")),
    ("修真世界", ("太皓星宫", "仙门", "飞升", "上界", "宗门", "掌教", "道侣", "仙朝")),
    ("星海大世界", ("星海", "联盟", "帝国", "侯爵", "皇室", "星尊", "星域", "舰队")),
)
ROLE_PROFILE_TAGS = {
    "舰灵": ["器灵/舰灵", "伴生女主", "常驻挂件"],
    "世界意志": ["世界意志", "高位女主"],
    "位面意志": ["位面意志", "高位女主"],
    "女皇": ["高位女主", "皇室线"],
    "皇后": ["高位女主", "皇室线", "人妻向"],
    "皇女": ["高位女主", "皇室线"],
    "长公主": ["高位女主", "皇室线"],
    "公主": ["高位女主", "皇室线"],
    "王妃": ["高位女主", "王妃线", "人妻向"],
    "圣女": ["高位女主", "圣女线"],
    "神女": ["高位女主", "神女线"],
    "师尊": ["高位女主", "师徒线"],
    "道侣": ["道侣线"],
    "远房表姐": ["亲缘边界", "曹贼向"],
    "表姐": ["亲缘边界", "曹贼向"],
    "表妹": ["亲缘边界"],
    "闺蜜": ["闺蜜线"],
    "侍女": ["侍奉线"],
    "侍妾": ["侍奉线"],
    "夫人": ["人妻向"],
    "秘书": ["都市职场线"],
    "助理": ["都市职场线"],
    "保镖": ["护卫线"],
    "管家": ["后宫管家"],
    "导师": ["导师线"],
    "掌教": ["宗门高位", "高位女主"],
    "宫主": ["宗门高位", "高位女主"],
    "宗主": ["宗门高位", "高位女主"],
}
RISK_RULES = (
    ("曹贼/人妻", ("夫人", "元配", "人妻", "皇后", "美妇", "表姐", "姑姑", "母后", "母亲")),
    ("亲缘/母女", ("女儿", "母女", "母后", "表妹", "表姐", "姑姑", "亲姑")),
    ("姐妹花", ("姐妹", "双胞胎", "三姐妹", "姐妹花")),
    ("师徒边界", ("师尊", "导师", "师徒")),
    ("侍奉调教", ("侍女", "侍妾", "侍寝", "禁脔", "顺从", "调教")),
    ("政治联姻", ("联姻", "婚约", "许配", "王妃", "皇后")),
    ("敌转后宫", ("臣服", "投降", "归顺", "敌对", "追杀", "镇压")),
    ("送女/进献", ("礼物", "送给", "进献", "献给", "赐予")),
    ("禁忌向", ("禁忌", "女儿", "共侍", "母女")),
)

NAME_ANCHOR_PATTERNS = (
    re.compile(r"(?:名叫|叫|名为)([\u4e00-\u9fff]{2,6})"),
    re.compile(rf"(?:{ROLE_PATTERN})([\u4e00-\u9fff]{{2,6}})"),
)
_SURNAME_PREFIX_PATTERN = "|".join(sorted(COMPOUND_SURNAMES, key=len, reverse=True))
_COMMON_SURNAME_PATTERN = "".join(sorted(COMMON_SURNAMES))
SURNAME_NAME_RE = re.compile(
    rf"(?:{_SURNAME_PREFIX_PATTERN}|[{_COMMON_SURNAME_PATTERN}])" r"[\u4e00-\u9fff]{1,3}"
)
HEADING_NAME_PATTERNS = (
    re.compile(
        r"^第[0-9零一二三四五六七八九十百千两]+[章节卷回幕篇]\s*"
        r"(?:初见|再见|再会|重逢)([\u4e00-\u9fff]{2,6})$"
    ),
    re.compile(
        r"^第[0-9零一二三四五六七八九十百千两]+[章节卷回幕篇]\s*"
        r"([\u4e00-\u9fff]{2,6})(?:心动|苏醒|归来|入场|出场|亮相)$"
    ),
    re.compile(
        r"^第[0-9零一二三四五六七八九十百千两]+[章节卷回幕篇]\s*"
        r"([\u4e00-\u9fff]{2,6})(?:现身|登场)$"
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
    direct_role_counts: Counter[str] = field(default_factory=Counter)
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
    if len(token) < 2 or len(token) > 6:
        return False
    if token in STOP_WORDS:
        return False
    if all(char in COMMON_FUNCTION_CHARS for char in token):
        return False
    if token.startswith(ORDINAL_PREFIXES):
        return False
    if token.endswith(GENERIC_SUFFIXES):
        return False
    if any(fragment in token for fragment in NON_NAME_SUBSTRINGS):
        return False
    if token[-1] in NON_NAME_ENDINGS:
        return False
    if token[0] in {"这", "那", "其", "某", "对", "向", "把", "将", "与", "和"}:
        return False
    if token[-1] in {"说", "道", "问", "笑", "看", "听", "着", "了", "的", "地", "声"}:
        return False
    if any(char in token for char in ("说道", "问道", "看着", "听着")):
        return False
    return True


def _top_role(stats: _EntityStats) -> str | None:
    if stats.direct_role_counts:
        return stats.direct_role_counts.most_common(1)[0][0]
    return stats.role_counts.most_common(1)[0][0] if stats.role_counts else None


def _has_compound_surname(name: str) -> bool:
    return any(name.startswith(surname) for surname in COMPOUND_SURNAMES)


def _has_common_surname(name: str) -> bool:
    if _has_compound_surname(name):
        return True
    return bool(name) and name[0] in COMMON_SURNAMES


def _has_direct_role_anchor(stats: _EntityStats) -> bool:
    return bool(stats.direct_role_counts)


def _looks_like_profile_character(stats: _EntityStats) -> bool:
    if not _looks_like_character_name(stats.name):
        return False

    direct_role = _has_direct_role_anchor(stats)
    has_surname = _has_common_surname(stats.name)
    has_title = stats.title_hits > 0

    if len(stats.name) == 2 and not (has_surname or direct_role or has_title):
        return False
    if len(stats.name) >= 5 and not (direct_role or has_surname or has_title):
        return False

    if not (has_surname or direct_role or has_title):
        if stats.anchored_hits < 2 or stats.chapter_hits < 4 or stats.romance_hits == 0:
            return False

    return True


def _is_high_confidence_character(stats: _EntityStats) -> bool:
    direct_role = _has_direct_role_anchor(stats)
    has_title = stats.title_hits > 0
    has_surname = _has_common_surname(stats.name)

    if direct_role or has_title:
        return True
    if len(stats.name) >= 3 and has_surname and stats.anchored_hits > 0:
        return True
    return False


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


def _dedupe_keep_order(items: list[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _profile_context(stats: _EntityStats, relation: _PairStats | None = None) -> str:
    parts = list(stats.snippets[:3])
    if relation and relation.evidence:
        parts.append(relation.evidence)
    return " ".join(_dedupe_keep_order(parts))


def _infer_worldline(profile_text: str, role: str | None = None) -> str:
    if role == "舰灵":
        return "诸天常驻"
    for label, keywords in WORLDLINE_RULES:
        if any(keyword in profile_text for keyword in keywords):
            return label
    return "待复核"


def _relation_summary(
    protagonist: str, name: str, relation: _PairStats | None, role: str | None
) -> str:
    if relation is None or relation.chapter_hits == 0:
        return f"与{protagonist}存在稳定同场，但感情线强度仍需正文复核。"

    if relation.conflict_hits > relation.chapter_hits:
        return f"和{protagonist}有明显对抗再收束倾向，偏敌转后宫线。"
    if role == "舰灵":
        return f"与{protagonist}几乎全程高频绑定，属于伴生挂件兼常驻女主位。"
    if relation.romance_hits > 0:
        return f"和{protagonist}的后宫候选边稳定，属于高频收束位女角。"
    if relation.chapter_hits >= 20:
        return f"和{protagonist}的同场频率很高，更像长期绑定的核心角色。"
    return f"和{protagonist}有持续互动，已进入核心人物网络。"


def _build_profile_tags(
    protagonist: str,
    stats: _EntityStats,
    relation: _PairStats | None = None,
    *,
    is_protagonist: bool = False,
) -> list[str]:
    role = _top_role(stats)
    profile_text = _profile_context(stats, relation)
    worldline = _infer_worldline(profile_text, role)

    tags: list[str] = []
    if is_protagonist:
        tags.extend(["诸天推土机", "资源滚雪球", "高位女主收集", "跨界争霸"])
        if stats.chapter_hits >= 200:
            tags.append("全书核心")
        return _dedupe_keep_order(tags)

    tags.extend(ROLE_PROFILE_TAGS.get(role or "", []))
    if worldline != "待复核":
        tags.append(f"{worldline}线")
    if stats.chapter_hits >= 100:
        tags.append("核心常驻")
    elif stats.chapter_hits >= 30:
        tags.append("高频女主")
    elif stats.chapter_hits >= 10:
        tags.append("中高频女角")

    if relation and relation.chapter_hits >= 20:
        tags.append("高频绑定")
    if relation and relation.romance_hits > 0:
        tags.append("感情线明显")
    if relation and relation.conflict_hits > relation.chapter_hits:
        tags.append("敌转后宫")
    if stats.early_hits > 0:
        tags.append("早期入场")
    if _heroine_score(stats) >= 12:
        tags.append("后宫核心")

    if role in {"皇后", "王妃", "夫人"}:
        tags.append("人妻向")
    if role in {"表姐", "远房表姐"}:
        tags.append("曹贼向")

    return _dedupe_keep_order(tags)


def _build_risk_tags(
    protagonist: str,
    stats: _EntityStats,
    relation: _PairStats | None = None,
    *,
    is_protagonist: bool = False,
) -> list[str]:
    tags: list[str] = []
    profile_text = _profile_context(stats, relation)

    for label, keywords in RISK_RULES:
        if any(keyword in profile_text for keyword in keywords):
            tags.append(label)

    if is_protagonist:
        if "曹贼向" in _build_profile_tags(protagonist, stats, relation, is_protagonist=True):
            tags.append("曹贼口味")
        tags.extend(["感情推进快", "收女节奏密"])

    if not tags:
        return ["无明显六雷硬证据"]
    return _dedupe_keep_order(tags)


def _character_summary(
    protagonist: str,
    stats: _EntityStats,
    relation: _PairStats | None = None,
    *,
    is_protagonist: bool = False,
) -> str:
    role = _top_role(stats)
    worldline = _infer_worldline(_profile_context(stats, relation), role)

    if is_protagonist:
        return (
            f"{protagonist}是图谱里的绝对中心节点，覆盖 {stats.chapter_hits} 章。"
            "路线就是拿时空星舰起家，一路跨界滚资源、扩势力、收高位女角，"
            "底色偏利己、果断、推土机。"
        )

    if role == "舰灵":
        return (
            f"{stats.name}是绑定在 {protagonist} 身边的舰灵型核心女角，"
            "更像全书常驻的外挂兼伴生女主，每次跨界推进几乎都能看到她的存在。"
        )
    if role in {"女皇", "皇后", "皇女", "长公主", "公主", "王妃"}:
        return (
            f"{stats.name}属于 {worldline} 的皇室/高位女主配置，"
            f"和 {protagonist} 的关系明显带着权力联盟并入后宫的味道。"
        )
    if role in {"圣女", "神女", "掌教", "宫主", "宗主", "师尊", "道侣"}:
        return (
            f"{stats.name}是 {worldline} 的高位修行系女角，"
            f"通常走征服、拉拢或双修收束的路线，是 {protagonist} 后宫网络里的高配置席位。"
        )
    if role in {"侍女", "侍妾", "秘书", "助理", "保镖", "管家", "导师"}:
        return (
            f"{stats.name}更偏 {worldline} 的功能型/侍奉型女角，"
            f"和 {protagonist} 的关系绑定稳定，爽点主要在长期跟随和服从位。"
        )
    return (
        f"{stats.name}是图谱里和 {protagonist} 绑定最稳的一批女性节点之一，"
        f"出场主要落在 {worldline}，角色定位偏 {role or '高频女角'}。"
    )


def _supporting_summary(
    protagonist: str, stats: _EntityStats, relation: _PairStats | None = None
) -> str:
    role = _top_role(stats)
    worldline = _infer_worldline(_profile_context(stats, relation), role)
    if role:
        return (
            f"{stats.name}是 {worldline} 线的重要节点，身份更接近 {role}。"
            f"他/她和 {protagonist} 的互动频繁，通常承担世界线推进或权力交接的功能。"
        )
    return (
        f"{stats.name}是 {worldline} 线的高频配角，和 {protagonist} 的共现密度较高，"
        "但具体关系仍建议结合正文复核。"
    )


def _profile_payload(
    protagonist: str,
    stats: _EntityStats,
    relation: _PairStats | None = None,
    *,
    is_protagonist: bool = False,
) -> dict:
    role = "男主" if is_protagonist else (_top_role(stats) or "身份待复核")
    worldline = _infer_worldline(
        _profile_context(stats, relation),
        None if is_protagonist else _top_role(stats),
    )
    tags = _build_profile_tags(protagonist, stats, relation, is_protagonist=is_protagonist)
    risk_tags = _build_risk_tags(protagonist, stats, relation, is_protagonist=is_protagonist)
    summary = _character_summary(protagonist, stats, relation, is_protagonist=is_protagonist)
    if not is_protagonist:
        summary = summary if stats.name != protagonist else summary

    payload = {
        "name": stats.name,
        "role": role,
        "worldline": worldline,
        "chapter_hits": stats.chapter_hits,
        "score": _character_score(stats),
        "evidence": stats.snippets[0] if stats.snippets else None,
        "summary": summary,
        "tags": tags,
        "risk_tags": risk_tags,
    }
    if relation is not None and not is_protagonist:
        payload["relation_summary"] = _relation_summary(
            protagonist, stats.name, relation, _top_role(stats)
        )
    return payload


def _normalize_candidate(candidate: str) -> str:
    normalized = candidate.lstrip("了又再")
    for role in sorted(ROLE_KEYWORDS, key=len, reverse=True):
        if normalized.startswith(role) and len(normalized) > len(role):
            normalized = normalized[len(role) :]
            break
    for suffix in TRAILING_NAME_NOISE:
        if normalized.endswith(suffix) and len(normalized) > len(suffix):
            normalized = normalized[: -len(suffix)]
    for role in sorted(ROLE_KEYWORDS, key=len, reverse=True):
        if normalized.endswith(role) and len(normalized) > len(role):
            normalized = normalized[: -len(role)]
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


def _extract_surname_names(text: str) -> list[str]:
    names: list[str] = []
    for match in SURNAME_NAME_RE.finditer(text):
        candidate = _normalize_candidate(match.group(0))
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
            for name in _extract_surname_names(sentence):
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
                    if f"{role}{name}" in context:
                        stats.direct_role_counts[role] += 1

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
            and _looks_like_profile_character(item)
        )
    ]
    return chapters, {item.name: item for item in _dedupe_names(filtered)}


def _protagonist_window_names(
    heading: str, content: str, protagonist: str
) -> dict[str, str | None]:
    names: dict[str, str | None] = {}
    title_names = _heading_names(heading)
    sentences = [
        sentence.strip() for sentence in SENTENCE_SPLIT_RE.split(content) if sentence.strip()
    ]

    if protagonist in f"{heading}\n{content}" and title_names:
        early_text = " ".join(sentences[:3])
        if any(hint in early_text for hint in FEMALE_HINTS + ROMANCE_HINTS + ROLE_KEYWORDS):
            for name in title_names:
                if name != protagonist:
                    names[name] = heading

    for index, sentence in enumerate(sentences):
        window = " ".join(sentences[max(0, index - 1) : index + 2])
        if protagonist not in window:
            continue
        if not any(hint in window for hint in FEMALE_HINTS + ROMANCE_HINTS + ROLE_KEYWORDS):
            continue

        for name in _extract_anchor_names(window):
            if name != protagonist:
                names[name] = None
        for name in _extract_surname_names(window):
            if name != protagonist and len(name) >= 3:
                names.setdefault(name, None)

    return names


def _collect_protagonist_heroine_stats(
    chapters: list[tuple[str, str]], protagonist: str
) -> dict[str, _EntityStats]:
    stats_map: dict[str, _EntityStats] = {}
    early_limit = max(30, len(chapters) // 8)

    for index, (heading, content) in enumerate(chapters, start=1):
        chapter_text = f"{heading}\n{content}"
        if protagonist not in chapter_text:
            continue

        candidate_names = _protagonist_window_names(heading, content, protagonist)
        if not candidate_names:
            continue

        for name, heading_hint in candidate_names.items():
            stats = stats_map.setdefault(name, _EntityStats(name=name))
            occurrences = chapter_text.count(name)
            if occurrences == 0:
                continue

            stats.raw_hits += occurrences
            stats.chapter_hits += 1
            if index <= early_limit:
                stats.early_hits += occurrences
            if heading_hint and name in heading_hint:
                stats.title_hits += 1

            context_text = chapter_text if heading_hint else content
            for context in _iter_contexts(context_text, name, window=28):
                if _is_anchored(name, context) or (heading_hint and name in heading_hint):
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
                    if f"{role}{name}" in context:
                        stats.direct_role_counts[role] += 1

                if (female_hits or romance_hits or role) and len(stats.snippets) < 3:
                    snippet = _clean_snippet(context)
                    if snippet not in stats.snippets:
                        stats.snippets.append(snippet)

    filtered = [
        item
        for item in stats_map.values()
        if (
            _has_direct_role_anchor(item)
            or item.title_hits > 0
            or (
                len(item.name) >= 3
                and _has_common_surname(item.name)
                and item.anchored_hits > 0
                and item.romance_hits > 0
            )
        )
        and _heroine_score(item) >= 4
    ]
    filtered.sort(
        key=lambda item: (_heroine_score(item), item.chapter_hits, item.raw_hits, len(item.name)),
        reverse=True,
    )
    return {item.name: item for item in filtered}


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
        if item.name != protagonist
        and _heroine_score(item) >= 4
        and (
            _has_direct_role_anchor(item)
            or item.title_hits > 0
            or (
                len(item.name) >= 3
                and _has_common_surname(item.name)
                and item.anchored_hits > 0
                and item.romance_hits > 0
            )
        )
    ]
    heroine_candidates.sort(
        key=lambda item: (_heroine_score(item), item.chapter_hits, item.raw_hits, len(item.name)),
        reverse=True,
    )

    selected = [protagonist] if protagonist_stats else []
    selected.extend(item.name for item in heroine_candidates[: max_nodes - 1])
    if len(selected) < max_nodes:
        others = sorted(
            (
                item
                for item in stats_map.values()
                if item.name not in selected and _is_high_confidence_character(item)
            ),
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
                "profile_method": "entity -> profile -> scan",
                "chunk_count": len(chapters),
                "protagonist": None,
                "protagonist_profile": None,
                "heroine_profiles": [],
                "supporting_profiles": [],
                "heroine_candidates": [],
                "core_characters": [],
                "relationship_highlights": [],
                "heroine_pool_estimate": 0,
            }
        )

    protagonist = _pick_protagonist(stats_map)
    heroine_stats_map = _collect_protagonist_heroine_stats(chapters, protagonist)
    if heroine_stats_map:
        heroine_names = list(heroine_stats_map)[:8]
        heroine_pool_estimate = max(len(heroine_stats_map), len(heroine_names) * 4)
        selected_names = [protagonist, *heroine_names]
        if len(selected_names) < max_nodes:
            others = sorted(
                (
                    item
                    for item in stats_map.values()
                    if item.name not in selected_names and _is_high_confidence_character(item)
                ),
                key=lambda item: (_character_score(item), item.chapter_hits, item.raw_hits),
                reverse=True,
            )
            selected_names.extend(item.name for item in others[: max_nodes - len(selected_names)])
    else:
        selected_names, heroine_names, heroine_pool_estimate = _pick_selected_names(
            stats_map, protagonist, max_nodes=max_nodes
        )

    selected_names = selected_names[:max_nodes]
    selected_stats = {}
    for name in selected_names:
        if name in heroine_stats_map:
            selected_stats[name] = heroine_stats_map[name]
        elif name in stats_map:
            selected_stats[name] = stats_map[name]
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

    protagonist_relations = {
        name: pair_stats.get(tuple(sorted((protagonist, name))))
        for name in selected_names
        if name != protagonist
    }
    profile_by_name: dict[str, dict] = {}
    for name in selected_names:
        stats = selected_stats[name]
        relation = protagonist_relations.get(name)
        profile = _profile_payload(
            protagonist,
            stats,
            relation,
            is_protagonist=name == protagonist,
        )
        if name != protagonist and name not in heroine_set:
            profile["summary"] = _supporting_summary(protagonist, stats, relation)
            profile["tags"] = _dedupe_keep_order(profile["tags"] + ["关键配角"])
        profile_by_name[name] = profile

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

        tags = list(profile_by_name.get(name, {}).get("tags", []))
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
                tags=_dedupe_keep_order(tags),
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
    reverse_id_map = {node_id: label for label, node_id in id_map.items()}
    relationship_highlights = sorted(
        (
            edge
            for edge in edges
            if protagonist
            in {
                reverse_id_map.get(edge.source, edge.source),
                reverse_id_map.get(edge.target, edge.target),
            }
        ),
        key=lambda item: (item.weight, item.chapter_hits),
        reverse=True,
    )[:8]
    heroine_profiles = [profile_by_name[node.label] for node in heroine_candidates]
    supporting_profiles = [
        profile_by_name[node.label]
        for node in core_characters
        if node.label != protagonist and node.label not in heroine_set
    ][:6]
    protagonist_profile = profile_by_name.get(protagonist)

    return LightweightGraph(
        nodes=nodes,
        edges=edges,
        metadata={
            "method": "mirofish-style-chunk-graph",
            "profile_method": "entity -> profile -> scan",
            "chunk_count": len(chapters),
            "protagonist": protagonist,
            "heroine_pool_estimate": heroine_pool_estimate,
            "protagonist_profile": protagonist_profile,
            "heroine_profiles": heroine_profiles,
            "supporting_profiles": supporting_profiles,
            "heroine_candidates": [
                {
                    **profile_by_name[node.label],
                    "category": node.category,
                    "node_tags": node.tags,
                }
                for node in heroine_candidates
            ],
            "core_characters": [
                {
                    **profile_by_name[node.label],
                    "category": node.category,
                    "node_tags": node.tags,
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
                    "tags": edge.tags,
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
