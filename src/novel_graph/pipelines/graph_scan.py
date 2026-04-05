from __future__ import annotations

from novel_graph.analysis.llm_graph import build_llm_graph, reduce_llm_graphs
from novel_graph.analysis.simple_graph import build_lightweight_graph
from novel_graph.domain.models import NovelInput, Provider, ScanMode, ScanResult
from novel_graph.rendering.markdown_renderer import heuristic_graph_scan_markdown


def run_graph_scan(
    novel_input: NovelInput, provider: Provider, model: str | None = None
) -> ScanResult:
    if provider == Provider.HEURISTIC:
        graph = build_lightweight_graph(novel_input.raw_text)
        return _graph_scan_result(novel_input, graph)

    graph = build_llm_graph(novel_input, model=model)
    return _graph_scan_result(novel_input, graph)


def run_graph_scan_segments(
    novel_input: NovelInput,
    segment_inputs: list[NovelInput],
    provider: Provider,
    model: str | None = None,
) -> ScanResult:
    if not segment_inputs:
        return run_graph_scan(novel_input, provider=provider, model=model)

    if provider == Provider.HEURISTIC:
        segment_graphs = [build_lightweight_graph(item.raw_text) for item in segment_inputs]
        graph = segment_graphs[0]
        if len(segment_graphs) > 1:
            graph.metadata["source_segments"] = len(segment_graphs)
        return _graph_scan_result(novel_input, graph)

    segment_graphs = [build_llm_graph(item, model=model) for item in segment_inputs]
    graph = reduce_llm_graphs(novel_input, segment_graphs, model=model)
    return _graph_scan_result(novel_input, graph)


def _graph_scan_result(novel_input: NovelInput, graph) -> ScanResult:
    markdown = heuristic_graph_scan_markdown(novel_input, graph=graph)
    return ScanResult(
        title=novel_input.title, mode=ScanMode.GRAPH, markdown=markdown, graph=graph
    )
