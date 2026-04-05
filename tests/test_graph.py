from novel_graph.analysis.simple_graph import build_lightweight_graph


def test_build_lightweight_graph_has_nodes() -> None:
    text = "林澈和夏音并肩直播。林澈再次找到夏音。千穗和白露讨论夏音的去留。"
    graph = build_lightweight_graph(text)
    assert len(graph.nodes) > 0
