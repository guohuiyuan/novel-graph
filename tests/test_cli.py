from pathlib import Path

from typer.testing import CliRunner

from novel_graph.cli import app


runner = CliRunner()


def test_scan_cli_generates_files(tmp_path: Path) -> None:
    input_file = tmp_path / "sample.md"
    input_file.write_text(
        "主角重生后决定挽救女团，没有绿帽但有前世线争议。", encoding="utf-8"
    )

    out_dir = tmp_path / "out"
    result = runner.invoke(
        app,
        [
            "scan",
            str(input_file),
            "--mode",
            "both",
            "--provider",
            "heuristic",
            "--output-dir",
            str(out_dir),
        ],
    )

    assert result.exit_code == 0
    assert (out_dir / "direct_scan.md").exists()
    assert (out_dir / "graph_scan.md").exists()
    assert (out_dir / "graph_snapshot.json").exists()
