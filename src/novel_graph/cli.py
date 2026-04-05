from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from novel_graph.domain.models import Provider, ScanMode
from novel_graph.io.input_loader import load_novel_input
from novel_graph.io.output_writer import write_graph_json, write_markdown
from novel_graph.pipelines.direct_scan import run_direct_scan
from novel_graph.pipelines.graph_scan import run_graph_scan

app = typer.Typer(help="把小说输入转换为结构化扫书 Markdown")


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
) -> None:
    novel_input = load_novel_input(input_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    if mode in (ScanMode.DIRECT, ScanMode.BOTH):
        direct_result = run_direct_scan(novel_input, provider=provider, model=model)
        direct_path = output_dir / "direct_scan.md"
        write_markdown(direct_path, direct_result.markdown)
        typer.echo(f"[direct] 已生成: {direct_path}")

    if mode in (ScanMode.GRAPH, ScanMode.BOTH):
        graph_result = run_graph_scan(novel_input, provider=provider, model=model)
        graph_path = output_dir / "graph_scan.md"
        write_markdown(graph_path, graph_result.markdown)
        typer.echo(f"[graph] 已生成: {graph_path}")

        if graph_result.graph is not None:
            graph_json_path = output_dir / "graph_snapshot.json"
            write_graph_json(graph_json_path, graph_result.graph)
            typer.echo(f"[graph] 图谱快照: {graph_json_path}")


if __name__ == "__main__":
    app()
