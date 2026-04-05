from __future__ import annotations

import re
from pathlib import Path
from typing import Annotated

import typer

from novel_graph.domain.models import Provider, ScanMode
from novel_graph.io.input_loader import load_novel_input
from novel_graph.io.output_writer import write_graph_json, write_markdown
from novel_graph.pipelines.direct_scan import run_direct_scan
from novel_graph.pipelines.graph_scan import run_graph_scan

app = typer.Typer(help="把小说输入转换为结构化扫书 Markdown")

_SEGMENT_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+|[^\s]")
_CHAPTER_HEADING_RE = re.compile(
    r"^(第[0-9零一二三四五六七八九十百千两]+[章节卷回幕篇]|chapter\s*\d+|#{1,3}\s+)",
    flags=re.IGNORECASE,
)


def _estimate_tokens(text: str) -> int:
    return len(_SEGMENT_TOKEN_RE.findall(text))


def _chapter_blocks(text: str) -> list[str]:
    lines = text.splitlines()
    blocks: list[str] = []
    current: list[str] = []

    for line in lines:
        is_heading = bool(_CHAPTER_HEADING_RE.match(line.strip()))
        if is_heading and current:
            block = "\n".join(current).strip()
            if block:
                blocks.append(block)
            current = [line]
            continue
        current.append(line)

    if current:
        block = "\n".join(current).strip()
        if block:
            blocks.append(block)

    if blocks:
        return blocks

    return [chunk.strip() for chunk in re.split(r"\n\s*\n", text) if chunk.strip()]


def _split_segments_by_token_budget(text: str, token_budget: int) -> list[str]:
    if token_budget <= 0:
        return [text]

    blocks = _chapter_blocks(text)
    if not blocks:
        return [text]

    segments: list[str] = []
    current_blocks: list[str] = []
    current_tokens = 0

    for block in blocks:
        block_tokens = _estimate_tokens(block)
        if current_blocks and current_tokens + block_tokens > token_budget:
            segments.append("\n\n".join(current_blocks).strip())
            current_blocks = [block]
            current_tokens = block_tokens
        else:
            current_blocks.append(block)
            current_tokens += block_tokens

    if current_blocks:
        segments.append("\n\n".join(current_blocks).strip())

    return [segment for segment in segments if segment]


@app.callback()
def main() -> None:
    """CLI entrypoint."""
    return None


@app.command("scan")
def scan(
    input_path: Annotated[
        str, typer.Argument(help="输入文件路径，支持 .epub/.txt/.md")
    ],
    mode: Annotated[
        ScanMode, typer.Option(help="扫书模式: direct / graph / both")
    ] = ScanMode.BOTH,
    provider: Annotated[
        Provider, typer.Option(help="生成方式: heuristic / openai")
    ] = Provider.HEURISTIC,
    output_dir: Annotated[Path, typer.Option(help="输出目录")] = Path("output"),
    model: Annotated[
        str | None, typer.Option(help="OpenAI模型名，可覆盖 OPENAI_MODEL")
    ] = None,
    segment_tokens: Annotated[
        int,
        typer.Option(
            help="每段近似token上限，默认40000。设为0表示不分段直接全量输入。"
        ),
    ] = 40000,
    segment_index: Annotated[int, typer.Option(help="要扫描的分段序号（从1开始）")] = 1,
) -> None:
    novel_input = load_novel_input(input_path)
    effective_segment_tokens = segment_tokens
    if provider == Provider.HEURISTIC and segment_tokens == 40000:
        effective_segment_tokens = 0

    segments = _split_segments_by_token_budget(
        novel_input.raw_text, effective_segment_tokens
    )

    if segment_index < 1 or segment_index > len(segments):
        raise typer.BadParameter(
            f"segment-index 超出范围: {segment_index}，当前共有 {len(segments)} 段"
        )

    selected_text = segments[segment_index - 1]
    selected_title = novel_input.title
    if len(segments) > 1:
        selected_title = f"{novel_input.title}（第{segment_index}/{len(segments)}段）"
        typer.echo(
            (
                f"[segment] 采用分段输入: {segment_index}/{len(segments)}，"
                f"约 {_estimate_tokens(selected_text)} tokens"
            )
        )

    segmented_input = type(novel_input)(
        source_path=novel_input.source_path,
        title=selected_title,
        raw_text=selected_text,
        author=novel_input.author,
        publisher=novel_input.publisher,
        published_at=novel_input.published_at,
        description=novel_input.description,
    )

    suffix = "" if len(segments) == 1 else f".part{segment_index}"
    output_dir.mkdir(parents=True, exist_ok=True)

    if mode in (ScanMode.DIRECT, ScanMode.BOTH):
        direct_result = run_direct_scan(segmented_input, provider=provider, model=model)
        direct_path = output_dir / f"direct_scan{suffix}.md"
        write_markdown(direct_path, direct_result.markdown)
        typer.echo(f"[direct] 已生成: {direct_path}")

    if mode in (ScanMode.GRAPH, ScanMode.BOTH):
        graph_result = run_graph_scan(segmented_input, provider=provider, model=model)
        graph_path = output_dir / f"graph_scan{suffix}.md"
        write_markdown(graph_path, graph_result.markdown)
        typer.echo(f"[graph] 已生成: {graph_path}")

        if graph_result.graph is not None:
            graph_json_path = output_dir / f"graph_snapshot{suffix}.json"
            write_graph_json(graph_json_path, graph_result.graph)
            typer.echo(f"[graph] 图谱快照: {graph_json_path}")


if __name__ == "__main__":
    app()
