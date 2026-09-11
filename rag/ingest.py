"""Add documents to the library.

Ingestion is idempotent: a file keyed the same way replaces its previous
version wholesale, and an unchanged file is skipped unless forced. Source
files are copied into the library directory so the database and its sources
travel together.
"""

from __future__ import annotations

import hashlib
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from rag import config
from rag.chunker import chunk as chunk_blocks
from rag.embeddings import get_embedder
from rag.extractors import SUPPORTED, ExtractionError, extract
from rag.store import Store, pack_vector

# Upload pipelines prefix files with a random hex id; drop it for the title.
_UPLOAD_PREFIX = re.compile(r"^[0-9a-f]{6,}[-_]")
_WEEK = re.compile(r"(?:week|wk|lecture|lec|topic|hoorcollege)[ _-]*(\d+(?:\.\d+)?)", re.I)
_EXERCISEY = re.compile(r"exercis|practic|opgave|tutorial|problem|answer|solution", re.I)


@dataclass
class IngestResult:
    doc_key: str
    title: str
    status: str          # "added" | "updated" | "skipped" | "failed"
    n_chunks: int = 0
    n_pages: int = 0
    detail: str = ""


@dataclass
class IngestReport:
    results: list[IngestResult] = field(default_factory=list)

    @property
    def added(self) -> int:
        return sum(r.status in {"added", "updated"} for r in self.results)

    @property
    def failed(self) -> list[IngestResult]:
        return [r for r in self.results if r.status == "failed"]

    @property
    def chunks(self) -> int:
        return sum(r.n_chunks for r in self.results)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def clean_title(filename: str) -> str:
    stem = _UPLOAD_PREFIX.sub("", Path(filename).stem)
    stem = stem.replace("_", " ").replace("-", " ")
    stem = re.sub(r"\s+", " ", stem).strip(" .")
    return stem or Path(filename).stem


def guess_week(title: str) -> str:
    match = _WEEK.search(title)
    return match.group(1) if match else ""


def guess_kind(title: str, text: str, suffix: str = "") -> str:
    """Exercises and answer keys behave differently from lecture material."""
    if suffix.lower() in {".vtt", ".srt"}:
        return "transcript"
    if _EXERCISEY.search(title):
        return "exercises"
    head = text[:1500]
    if _EXERCISEY.search(head) and len(_EXERCISEY.findall(head)) > 1:
        return "exercises"
    return "lecture"


def ingest_file(
    store: Store,
    path: Path,
    *,
    course: str = "",
    week: str | None = None,
    kind: str | None = None,
    tags: str = "",
    doc_key: str | None = None,
    force: bool = False,
    copy_source: bool = True,
    embed: bool = True,
    backend: str | None = None,
) -> IngestResult:
    path = Path(path)
    title = clean_title(path.name)
    key = doc_key or clean_title(path.name).lower().replace(" ", "-")

    if not path.exists():
        return IngestResult(key, title, "failed", detail=f"No such file: {path}")
    if path.suffix.lower() not in SUPPORTED:
        return IngestResult(key, title, "failed", detail=f"Unsupported type '{path.suffix}'")

    sha = _sha256(path)
    existing = store.get_document(key)
    if existing is not None and existing["sha256"] == sha and not force:
        return IngestResult(key, title, "skipped", detail="unchanged (use --force to reindex)")

    try:
        blocks = extract(path)
    except ExtractionError as exc:
        return IngestResult(key, title, "failed", detail=str(exc))

    chunks = chunk_blocks(blocks)
    if not chunks:
        return IngestResult(key, title, "failed", detail="produced no chunks")

    full_text = "\n".join(b.text for b in blocks)
    page_label = blocks[0].label or "page"
    n_pages = max((b.page for b in blocks), default=0)

    stored_path = path
    if copy_source:
        library = config.library_dir()
        library.mkdir(parents=True, exist_ok=True)
        stored_path = library / f"{key}{path.suffix.lower()}"
        if path.resolve() != stored_path.resolve():
            shutil.copy2(path, stored_path)

    doc_id = store.upsert_document(
        doc_key=key,
        title=title,
        source_path=str(stored_path),
        kind=kind or guess_kind(title, full_text, path.suffix),
        course=course,
        week=week if week is not None else guess_week(title),
        tags=tags,
        sha256=sha,
        page_label=page_label,
        n_pages=n_pages,
        added_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        meta={"original_filename": path.name},
    )
    chunk_ids = store.add_chunks(doc_id, chunks)

    if embed:
        embedder = get_embedder(backend)
        if embedder is not None:
            vectors = embedder.embed([c.text for c in chunks])
            store.add_embeddings(
                [
                    (cid, embedder.name, len(vec), pack_vector(vec))
                    for cid, vec in zip(chunk_ids, vectors)
                ]
            )

    return IngestResult(
        doc_key=key,
        title=title,
        status="updated" if existing is not None else "added",
        n_chunks=len(chunks),
        n_pages=n_pages,
    )


def ingest_paths(store: Store, paths: list[Path], **kwargs) -> IngestReport:
    """Ingest files and directories (recursively, supported types only)."""
    report = IngestReport()
    for target in _expand(paths):
        report.results.append(ingest_file(store, target, **kwargs))
    return report


def _expand(paths: list[Path]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            out.extend(
                sorted(
                    f for f in p.rglob("*")
                    if f.is_file() and f.suffix.lower() in SUPPORTED
                )
            )
        else:
            out.append(p)
    return out
