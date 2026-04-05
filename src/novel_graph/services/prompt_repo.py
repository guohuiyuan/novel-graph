from __future__ import annotations

from pathlib import Path


def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_prompt(prompt_name: str) -> str:
    path = package_root() / "prompts" / prompt_name
    if not path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {path}")
    return path.read_text(encoding="utf-8")


def read_resource(name: str) -> str:
    path = package_root() / "resources" / name
    if not path.exists():
        raise FileNotFoundError(f"资源文件不存在: {path}")
    return path.read_text(encoding="utf-8")
