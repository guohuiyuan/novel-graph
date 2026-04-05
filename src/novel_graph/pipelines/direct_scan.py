from __future__ import annotations

from novel_graph.domain.models import NovelInput, Provider, ScanMode, ScanResult
from novel_graph.rendering.markdown_renderer import heuristic_scan_markdown
from novel_graph.services.llm_client import LLMClient
from novel_graph.services.prompt_repo import read_prompt, read_resource


SYSTEM_PROMPT = "你是专业的后宫文扫书编辑，输出必须是结构化中文Markdown。"


def run_direct_scan(
    novel_input: NovelInput, provider: Provider, model: str | None = None
) -> ScanResult:
    if provider == Provider.HEURISTIC:
        markdown = heuristic_scan_markdown(novel_input.title, novel_input.raw_text)
        return ScanResult(
            title=novel_input.title, mode=ScanMode.DIRECT, markdown=markdown
        )

    prompt_template = read_prompt("direct_scan.md")
    requirements = read_resource("scan_requirements.md")
    term_reference = read_resource("term_reference.md")
    style_reference = read_resource("style_reference.md")

    prompt = prompt_template.format(
        title=novel_input.title,
        requirements=requirements,
        term_reference=term_reference,
        style_reference=style_reference,
        text_excerpt=novel_input.raw_text[:16000],
    )

    llm = LLMClient(model=model)
    markdown = llm.generate_markdown(system_prompt=SYSTEM_PROMPT, user_prompt=prompt)
    return ScanResult(title=novel_input.title, mode=ScanMode.DIRECT, markdown=markdown)
