from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from ebooklib import ITEM_DOCUMENT, epub

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


def _first_metadata_value(book: epub.EpubBook, namespace: str, name: str) -> str | None:
    values = book.get_metadata(namespace, name)
    if not values:
        return None

    raw = values[0][0]
    if raw is None:
        return None

    text = str(raw).strip()
    return text or None


def _read_epub(path: Path) -> tuple[str, dict[str, str | None]]:
    book = epub.read_epub(str(path))
    chunks: list[str] = []
    for item in book.get_items():
        if item.get_type() != ITEM_DOCUMENT:
            continue
        soup = BeautifulSoup(item.get_body_content(), "html.parser")
        text = soup.get_text("\n", strip=True)
        if text:
            chunks.append(text)

    metadata = {
        "title": _first_metadata_value(book, "DC", "title"),
        "author": _first_metadata_value(book, "DC", "creator"),
        "publisher": _first_metadata_value(book, "DC", "publisher"),
        "published_at": _first_metadata_value(book, "DC", "date"),
        "description": _first_metadata_value(book, "DC", "description"),
    }
    return _clean_text("\n\n".join(chunks)), metadata


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
    title = _clean_title(path)
    author: str | None = None
    publisher: str | None = None
    published_at: str | None = None
    description: str | None = None

    if suffix == ".epub":
        raw_text, metadata = _read_epub(path)
        title = metadata["title"] or title
        author = metadata["author"]
        publisher = metadata["publisher"]
        published_at = metadata["published_at"]
        description = metadata["description"]
    elif suffix in {".txt", ".md", ".markdown"}:
        raw_text = _read_text_like(path)
    else:
        raise ValueError(f"暂不支持的输入格式: {suffix}")

    if not raw_text:
        raise ValueError("输入文本为空，无法生成扫书")

    return NovelInput(
        source_path=path,
        title=title,
        raw_text=raw_text,
        author=author,
        publisher=publisher,
        published_at=published_at,
        description=description,
    )
