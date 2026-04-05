from __future__ import annotations

from novel_graph.analysis.book_profile import BookProfile, CharacterDigest, build_book_profile
from novel_graph.analysis.simple_graph import summarize_graph
from novel_graph.domain.models import LightweightGraph, NovelInput


def _render_character_lines(items: list[CharacterDigest], fallback: str) -> list[str]:
    if not items:
        return [fallback]

    lines: list[str] = []
    for index, item in enumerate(items, start=1):
        role = item.role or "身份待复核"
        traits = f"；标签：{' / '.join(item.traits)}" if item.traits else ""
        lines.append(
            f"{index}. {item.name}：{role}。{item.summary}（证据：{item.chapter_hint}）{traits}"
        )
    return lines


def _render_grade_block(profile: BookProfile) -> str:
    order = ("情节", "文笔", "感情", "车速", "人物刻画", "新意", "压抑度", "总评")
    return "\n".join(f"- **{label}：{profile.grades[label]}**" for label in order)


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

PS：当前本地抽取结果对应 **{profile.heroine_pool_label}** 级别的高相关女角规模，
长名单可继续人工核表补全。

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
