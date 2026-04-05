from pathlib import Path

from novel_graph.analysis.simple_graph import build_lightweight_graph, summarize_graph
from novel_graph.domain.models import NovelInput
from novel_graph.rendering.markdown_renderer import heuristic_graph_scan_markdown

SAMPLE_TEXT = """第一章 初见云绮君
秦烽在大齐王都见到了云绮君。云绮君身为公主，对秦烽说道愿意合作。

第二章 欧阳芷瑜心动
欧阳芷瑜在宴会上陪着秦烽，心动之余主动示好。秦烽看着欧阳芷瑜点头。

第三章 再会云绮君
秦烽再次见到云绮君，公主云绮君与秦烽并肩而行，气氛暧昧。

第四章 羽澶现身
舰灵羽澶在星舰中苏醒。羽澶陪伴秦烽出手，舰灵羽澶对秦烽说道已经锁定目标。
"""


def test_build_lightweight_graph_uses_character_candidates() -> None:
    graph = build_lightweight_graph(SAMPLE_TEXT)

    labels = {node.label for node in graph.nodes}
    assert "秦烽" in labels
    assert "云绮君" in labels
    assert "欧阳芷瑜" in labels
    assert "说着" not in labels

    assert graph.metadata["protagonist"] == "秦烽"
    heroine_names = {item["name"] for item in graph.metadata["heroine_candidates"]}
    assert "云绮君" in heroine_names

    summary = summarize_graph(graph)
    assert "秦烽" in summary
    assert "云绮君" in summary


def test_heuristic_graph_scan_markdown_renders_graph_sections(tmp_path: Path) -> None:
    novel_input = NovelInput(
        source_path=tmp_path / "sample.md",
        title="示例小说",
        raw_text=SAMPLE_TEXT,
        author="测试作者",
    )
    graph = build_lightweight_graph(SAMPLE_TEXT)

    markdown = heuristic_graph_scan_markdown(novel_input, graph)

    assert "知识图谱速览" in markdown
    assert "核心女主候选" in markdown
    assert "云绮君" in markdown
    assert "高频关系边" in markdown
