from __future__ import annotations

from pathlib import Path
import re

from ebooklib import ITEM_DOCUMENT
from bs4 import BeautifulSoup
from ebooklib import epub

from novel_graph.domain.models import NovelInput


def _clean_title(path: Path) -> str:
    # Normalize noisy download suffixes while preserving meaningful title chunks.
    title = path.stem
    title = re.sub(r"_[^_]{1,16}_\d{8}_\d{6}$", "", title)
    title = title.replace("_", " ").strip()
    return title or path.stem


def _clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _read_epub(path: Path) -> str:
    book = epub.read_epub(str(path))
    chunks: list[str] = []
    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_body_content(), "html.parser")
        text = soup.get_text("\n", strip=True)
        if text:
            chunks.append(text)
    return _clean_text("\n\n".join(chunks))


def _read_text_like(path: Path) -> str:
    # utf-8 first, then a permissive fallback for mixed-source web novels.
    try:
        return _clean_text(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError:
        return _clean_text(path.read_text(encoding="utf-8", errors="ignore"))


def load_novel_input(input_path: str | Path) -> NovelInput:
    path = Path(input_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"输入文件不存在: {path}")

    suffix = path.suffix.lower()
    if suffix == ".epub":
        raw_text = _read_epub(path)
    elif suffix in {".txt", ".md", ".markdown"}:
        raw_text = _read_text_like(path)
    else:
        raise ValueError(f"暂不支持的输入格式: {suffix}")

    if not raw_text:
        raise ValueError("输入文本为空，无法生成扫书")

    return NovelInput(source_path=path, title=_clean_title(path), raw_text=raw_text)
