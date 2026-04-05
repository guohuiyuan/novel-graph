from __future__ import annotations

import json

from novel_graph.analysis.simple_graph import build_lightweight_graph
from novel_graph.domain.models import NovelInput, Provider, ScanMode, ScanResult
from novel_graph.rendering.markdown_renderer import heuristic_scan_markdown
from novel_graph.services.llm_client import LLMClient
from novel_graph.services.prompt_repo import read_prompt, read_resource

SYSTEM_PROMPT = (
    "你是专业的后宫文扫书编辑，擅长把知识图谱摘要融合进扫书报告。"
    "输出必须是结构化中文Markdown。"
)


def run_graph_scan(
    novel_input: NovelInput, provider: Provider, model: str | None = None
) -> ScanResult:
    graph = build_lightweight_graph(novel_input.raw_text)

    if provider == Provider.HEURISTIC:
        markdown = heuristic_scan_markdown(novel_input, graph=graph)
        return ScanResult(
            title=novel_input.title, mode=ScanMode.GRAPH, markdown=markdown, graph=graph
        )

    prompt_template = read_prompt("graph_scan.md")
    requirements = read_resource("scan_requirements.md")
    term_reference = read_resource("term_reference.md")
    style_reference = read_resource("style_reference.md")

    prompt = prompt_template.format(
        title=novel_input.title,
        requirements=requirements,
        term_reference=term_reference,
        style_reference=style_reference,
        graph_json=json.dumps(graph.to_dict(), ensure_ascii=False, indent=2),
        text_excerpt=novel_input.raw_text,
    )

    llm = LLMClient(model=model)
    markdown = llm.generate_markdown(system_prompt=SYSTEM_PROMPT, user_prompt=prompt)
    return ScanResult(
        title=novel_input.title, mode=ScanMode.GRAPH, markdown=markdown, graph=graph
    )
