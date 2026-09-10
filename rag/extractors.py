"""Turn source files into a flat list of located text blocks.

Every block remembers the page or slide it came from so answers can cite
"Lecture 2, slide 14" instead of pointing vaguely at a whole deck.
"""

from __future__ import annotations

import csv
import html.parser
import io
from dataclasses import dataclass
from pathlib import Path

from rag.normalize import clean

SUPPORTED = {".pdf", ".pptx", ".docx", ".md", ".markdown", ".txt", ".html", ".htm", ".csv"}


class ExtractionError(RuntimeError):
    pass


@dataclass
class Block:
    """A run of text plus where in the document it lives."""

    text: str
    page: int          # 1-based page / slide number; 0 when the format has no pages
    label: str = ""    # "page" or "slide"


def _pdf(path: Path) -> list[Block]:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - depends on install
        raise ExtractionError("PDF support needs 'pypdf' (pip install pypdf)") from exc

    blocks: list[Block] = []
    reader = PdfReader(str(path))
    for i, page in enumerate(reader.pages, start=1):
        text = clean(page.extract_text() or "")
        if text:
            blocks.append(Block(text=text, page=i, label="page"))
    if not blocks:
        raise ExtractionError(
            f"No text found in {path.name}. If it is a scan, OCR it first."
        )
    return blocks


def _pptx(path: Path) -> list[Block]:
    try:
        from pptx import Presentation
    except ImportError as exc:  # pragma: no cover - depends on install
        raise ExtractionError("PPTX support needs 'python-pptx' (pip install python-pptx)") from exc

    blocks: list[Block] = []
    deck = Presentation(str(path))
    for i, slide in enumerate(deck.slides, start=1):
        parts: list[str] = []
        for shape in slide.shapes:
            parts.extend(_shape_text(shape))
        notes = ""
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
        if notes:
            parts.append(f"[Speaker notes] {notes}")
        text = clean("\n".join(p for p in parts if p.strip()))
        if text:
            blocks.append(Block(text=text, page=i, label="slide"))
    if not blocks:
        raise ExtractionError(f"No text found in {path.name}.")
    return blocks


def _shape_text(shape) -> list[str]:
    """Recurse through groups and tables, which hold most of the content in decks."""
    out: list[str] = []
    if shape.shape_type == 6 and hasattr(shape, "shapes"):  # GROUP
        for child in shape.shapes:
            out.extend(_shape_text(child))
        return out
    if getattr(shape, "has_text_frame", False):
        out.append(shape.text_frame.text)
    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                out.append(" | ".join(cells))
    return out


def _docx(path: Path) -> list[Block]:
    try:
        import docx
    except ImportError as exc:  # pragma: no cover - depends on install
        raise ExtractionError("DOCX support needs 'python-docx' (pip install python-docx)") from exc

    document = docx.Document(str(path))
    parts = [p.text for p in document.paragraphs]
    for table in document.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    text = clean("\n".join(parts))
    if not text:
        raise ExtractionError(f"No text found in {path.name}.")
    return [Block(text=text, page=0)]


class _HTMLText(html.parser.HTMLParser):
    _SKIP = {"script", "style", "head"}

    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self._skipping = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skipping += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skipping:
            self._skipping -= 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "h4", "br", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skipping:
            self.parts.append(data)


def _html(path: Path) -> list[Block]:
    parser = _HTMLText()
    parser.feed(path.read_text(encoding="utf-8", errors="replace"))
    text = clean("".join(parser.parts))
    if not text:
        raise ExtractionError(f"No text found in {path.name}.")
    return [Block(text=text, page=0)]


def _csv(path: Path) -> list[Block]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    rows = list(csv.reader(io.StringIO(raw)))
    text = clean("\n".join(" | ".join(r) for r in rows if any(c.strip() for c in r)))
    if not text:
        raise ExtractionError(f"No rows found in {path.name}.")
    return [Block(text=text, page=0)]


def _plain(path: Path) -> list[Block]:
    text = clean(path.read_text(encoding="utf-8", errors="replace"))
    if not text:
        raise ExtractionError(f"{path.name} is empty.")
    return [Block(text=text, page=0)]


_HANDLERS = {
    ".pdf": _pdf,
    ".pptx": _pptx,
    ".docx": _docx,
    ".md": _plain,
    ".markdown": _plain,
    ".txt": _plain,
    ".html": _html,
    ".htm": _html,
    ".csv": _csv,
}


def extract(path: Path) -> list[Block]:
    """Read `path` into located, cleaned text blocks."""
    suffix = path.suffix.lower()
    handler = _HANDLERS.get(suffix)
    if handler is None:
        raise ExtractionError(
            f"Cannot read '{suffix or path.name}'. Supported: {', '.join(sorted(SUPPORTED))}"
        )
    return handler(path)
