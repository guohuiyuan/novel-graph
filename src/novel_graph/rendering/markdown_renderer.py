from __future__ import annotations

from novel_graph.analysis.keywords import (
    infer_defense_level,
    infer_depress_points,
    infer_tags,
    infer_thunder_points,
)
from novel_graph.analysis.simple_graph import summarize_graph
from novel_graph.domain.models import LightweightGraph


def heuristic_scan_markdown(
    title: str, text: str, graph: LightweightGraph | None = None
) -> str:
    thunder = infer_thunder_points(text)
    depress = infer_depress_points(text)
    tags = infer_tags(text)
    defense = infer_defense_level(len(thunder), len(depress))

    verdict = "可尝试" if not thunder else "谨慎阅读"
    thunder_lines = [
        (
            f"- [{item.name}] 文本中出现了与该雷点相关的明确风险行为线索，"
            f"但当前仅能基于关键词判断，需人工补全“谁对谁做了什么事”（风险: {item.level}，证据: {'/'.join(item.evidence)}）"
        )
        for item in thunder
    ]
    depress_lines = [
        (
            f"- [{item.name}] 出现郁闷相关情节线索，建议结合具体角色和事件补全描述"
            f"（强度: {item.level}，证据: {'/'.join(item.evidence)}）"
        )
        for item in depress
    ]

    if not thunder_lines:
        thunder_lines = ["- 暂未命中明确雷点关键词（仅启发式检测，需人工复核）"]
    if not depress_lines:
        depress_lines = ["- 暂未命中明显郁闷点关键词（仅启发式检测，需人工复核）"]

    graph_summary = summarize_graph(graph) if graph else "本流程未使用图谱增强。"

    return f"""# {title} - 扫书

## 书籍信息简介
- 书名: {title}
- 题材标签: {' / '.join(tags)}
- 输出方式: 启发式规则 + 关键词证据

## 简介
- 建议补充 2-4 句主线简介（当前为自动草稿，需人工润色）

## 男主
- 信息不足，需人工复核

## 女主（含准女主）
- 已确认女主:
    - 信息不足，需人工复核
- 准女主:
    - 信息不足，需人工复核（请按“非wrq + 戏份高 + 感情交集”规则判定）

## 一句话结论
- 结论: {verdict}

## 卖点速览
- 正向卖点: 请结合剧情手动补充（当前版本以风险识别为主）
- 潜在争议: 重点关注雷点与郁闷点命中项

## 剧情与人物
- 建议补充三句话版本剧情梗概
- 建议补充男女主关系推进节奏
- 图谱摘要: {graph_summary}

## 防御档位
- 推荐防御档位: {defense}

## 雷点排查（六雷）
{chr(10).join(thunder_lines)}

## 郁闷点排查
{chr(10).join(depress_lines)}

## 名词详解
- 防御体系参考: 神防之上 / 神防 / 重甲 / 布甲 / 轻甲 / 低防 / 负防
- 本工具默认不把郁闷点夸大为雷点，雷点仅限六雷

## 适合谁看 / 慎入人群
- 适合: 能接受本报告中已标注郁闷点的读者
- 慎入: 对任何已命中雷点零容忍的读者

## 结语
- 当前结果为自动草稿，请重点人工校对“雷点行为主体”和“准女主判定证据”。
""".strip()
