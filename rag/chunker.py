"""Split located blocks into retrieval-sized chunks.

Two things matter for study material. Exercises must not be cut in half — a
question separated from its answer is useless — so explicit exercise markers
start a new chunk. And every chunk keeps a human-readable section label, so a
citation reads "Exercise 2.3" rather than "chunk 47".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rag.extractors import Block

TARGET_CHARS = 1400   # ~350 tokens: big enough for a full slide or exercise
MAX_CHARS = 2600
OVERLAP_CHARS = 200

# "Exercise 2.1", "2.3 A firm located on a riverbank", "Question 4"
_EXERCISE = re.compile(
    r"^[ \t]*(?:(?:Exercise|Question|Problem|Opgave)\s+)?(\d+\.\d+|\d+\))(?=[ \t)])",
    re.MULTILINE,
)
_HEADINGY = re.compile(r"^[A-Z0-9][^.!?]{2,79}$")
_PARA = re.compile(r"\n\s*\n")
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z(])")


@dataclass
class Chunk:
    text: str
    page_start: int
    page_end: int
    section: str


def _heading_for(text: str) -> str:
    """Best-effort section title: the first line that looks like a title."""
    # An exercise number is the most useful label this material offers.
    lead = _EXERCISE.match(text)
    if lead:
        return f"Exercise {lead.group(1).rstrip(')')}"
    for line in text.split("\n")[:3]:
        line = line.strip().lstrip("-").strip()
        if not line or line.isdigit():
            continue
        # Slide numbers often lead the text block; skip them.
        line = re.sub(r"^\d{1,3}\s+", "", line).strip()
        if line and _HEADINGY.match(line):
            return line[:120]
        break
    return ""


def _split_on_exercises(block: Block) -> list[Block]:
    """Break a block apart at exercise numbers so each problem stands alone."""
    starts = [m.start() for m in _EXERCISE.finditer(block.text)]
    # A single marker at position 0 is just the block's own title, not a split.
    starts = [s for s in starts if s > 0]
    if not starts:
        return [block]
    bounds = [0, *starts, len(block.text)]
    out: list[Block] = []
    for lo, hi in zip(bounds, bounds[1:]):
        piece = block.text[lo:hi].strip()
        if piece:
            out.append(Block(text=piece, page=block.page, label=block.label))
    return out


def _hard_split(text: str) -> list[str]:
    """Cut an oversized unit on paragraph, then sentence, then hard boundaries."""
    pieces = [p for p in _PARA.split(text) if p.strip()]
    if len(pieces) == 1:
        pieces = _SENTENCE.split(text)

    out: list[str] = []
    buf = ""
    for piece in pieces:
        candidate = f"{buf}\n\n{piece}" if buf else piece
        if len(candidate) <= MAX_CHARS:
            buf = candidate
            continue
        if buf:
            out.append(buf)
        while len(piece) > MAX_CHARS:
            out.append(piece[:MAX_CHARS])
            piece = piece[MAX_CHARS - OVERLAP_CHARS:]
        buf = piece
    if buf:
        out.append(buf)
    return out


def chunk(blocks: list[Block]) -> list[Chunk]:
    """Pack blocks into chunks of roughly TARGET_CHARS, preserving location."""
    units: list[Block] = []
    for block in blocks:
        units.extend(_split_on_exercises(block))

    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_len = 0
    page_start = page_end = 0
    section = ""

    def flush() -> None:
        nonlocal buf, buf_len, section
        if buf:
            body = "\n\n".join(buf).strip()
            if body:
                chunks.append(Chunk(body, page_start, page_end, section))
        buf, buf_len = [], 0
        section = ""

    for unit in units:
        for piece in _hard_split(unit.text):
            # Starting a fresh chunk: record where it begins and what it is about.
            if not buf:
                page_start = page_end = unit.page
                section = _heading_for(piece)

            if buf and buf_len + len(piece) > TARGET_CHARS:
                flush()
                page_start = page_end = unit.page
                section = _heading_for(piece)

            # A later piece may carry the only usable label (an exercise number
            # merged in behind an untitled intro paragraph).
            if not section:
                section = _heading_for(piece)

            buf.append(piece)
            buf_len += len(piece)
            page_end = unit.page

            if buf_len >= TARGET_CHARS:
                flush()

    flush()
    return chunks
