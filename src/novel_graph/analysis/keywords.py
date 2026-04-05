from __future__ import annotations

from dataclasses import dataclass
from collections import Counter
import re


@dataclass(slots=True)
class SignalMatch:
    name: str
    level: str
    evidence: list[str]


THUNDER_KEYWORDS: dict[str, list[str]] = {
    "绿帽": ["绿帽", "被绿", "牛头人"],
    "死女": ["女主死亡", "女主死", "准女主死亡", "红颜陨落"],
    "送女": ["送女", "拱手让人", "让给别人"],
    "背叛": ["背叛", "叛变", "转投他人"],
    "wrq": ["万人骑", "wrq"],
    "龟作": ["知雷写雷", "龟作"],
}

DEPRESS_KEYWORDS: dict[str, list[str]] = {
    "前世雷": ["前世", "原故事线", "重生前"],
    "px/fc/非初": ["非处", "fc", "非初", "破鞋", "嫁过人"],
    "亵女": ["调戏", "占便宜", "摸", "看光"],
    "漏女": ["没收", "漏女", "暧昧到结局"],
    "拒女": ["拒绝表白", "拒女", "无视爱意"],
    "惧女": ["惧内", "言听计从", "不敢反抗"],
    "虐主": ["虐主", "被辱", "忍辱负重"],
    "百合": ["百合", "贴贴"],
    "面具": ["面具", "换身份攻略"],
    "分身": ["分身", "化身", "傀儡分身"],
    "生孩子": ["生孩子", "儿子", "怀孕"],
}

DEFENSE_HINTS: list[tuple[str, str]] = [
    ("神防之上", "无视任何雷点"),
    ("神防", "可抗大部分郁闷"),
    ("重甲", "可抗绝大多数郁闷"),
    ("布甲", "可抗中度郁闷"),
    ("轻甲", "可抗轻度郁闷"),
    ("低防", "仅能接受小郁闷"),
    ("负防", "偏好无雷无郁闷"),
]

STOP_WORDS = {
    "我们",
    "他们",
    "她们",
    "你们",
    "不是",
    "这个",
    "那个",
    "主角",
    "女主",
    "男人",
    "女人",
    "小说",
    "故事",
    "时候",
    "因为",
    "然后",
    "自己",
    "没有",
    "一个",
    "一些",
    "可以",
    "已经",
    "如果",
    "但是",
    "还是",
    "开始",
    "后来",
    "最终",
    "其中",
    "对于",
    "进行",
    "出现",
    "非常",
    "可能",
    "需要",
    "当前",
    "通过",
    "以及",
    "这种",
    "那种",
    "这样",
    "那样",
    "里面",
    "外面",
    "成为",
    "作为",
    "其中",
    "作者",
    "读者",
    "角色",
    "情节",
    "剧情",
    "关系",
    "章节",
    "描写",
    "设定",
    "平台",
    "字数",
    "完结",
    "连载",
}


def _collect_matches(text: str, mapping: dict[str, list[str]]) -> list[SignalMatch]:
    matches: list[SignalMatch] = []
    lower = text.lower()
    for label, keywords in mapping.items():
        hit_terms = [term for term in keywords if term.lower() in lower]
        if hit_terms:
            level = "高" if len(hit_terms) >= 2 else "中"
            matches.append(SignalMatch(name=label, level=level, evidence=hit_terms))
    return matches


def infer_thunder_points(text: str) -> list[SignalMatch]:
    return _collect_matches(text, THUNDER_KEYWORDS)


def infer_depress_points(text: str) -> list[SignalMatch]:
    return _collect_matches(text, DEPRESS_KEYWORDS)


def infer_defense_level(thunder_count: int, depress_count: int) -> str:
    if thunder_count > 0:
        return "负防及以下（存在雷点，不建议低防读者）"
    if depress_count >= 8:
        return "重甲"
    if depress_count >= 5:
        return "布甲"
    if depress_count >= 3:
        return "轻甲"
    if depress_count >= 1:
        return "低防"
    return "负防友好（近似无雷无郁闷）"


def infer_tags(text: str) -> list[str]:
    tag_rules = {
        "后宫": ["后宫", "全收", "多女主"],
        "重生": ["重生", "回到过去", "再来一次"],
        "穿越": ["穿越", "异世界", "魂穿"],
        "都市": ["都市", "现实世界", "现代"],
        "奇幻": ["魔法", "修仙", "神明", "异能"],
        "无限": ["无限", "诸天", "副本"],
    }
    lower = text.lower()
    tags: list[str] = []
    for tag, words in tag_rules.items():
        if any(word.lower() in lower for word in words):
            tags.append(tag)
    return tags or ["待补充"]


def top_candidate_names(text: str, limit: int = 16) -> list[str]:
    candidates = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
    counter = Counter(name for name in candidates if name not in STOP_WORDS)
    ranked = [name for name, _ in counter.most_common(limit * 3)]
    uniq: list[str] = []
    for name in ranked:
        if name in uniq:
            continue
        if any(name in x or x in name for x in uniq):
            continue
        uniq.append(name)
        if len(uniq) >= limit:
            break
    return uniq
