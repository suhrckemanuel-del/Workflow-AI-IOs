"""HTTP surface for the course RAG library."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel

from rag import config
from rag.answer import MODES, MissingAPIKey, ask
from rag.extractors import SUPPORTED
from rag.ingest import ingest_file
from rag.retriever import Filters, Retriever
from rag.store import Hit, Store

router = APIRouter(prefix="/rag", tags=["rag"])


def _store() -> Store:
    return Store(config.db_path())


class Passage(BaseModel):
    chunk_id: int
    title: str
    citation: str
    section: str
    page_start: int
    page_end: int
    kind: str
    course: str
    week: str
    score: float
    text: str


class SearchResponse(BaseModel):
    query: str
    passages: list[Passage]


class AskRequest(BaseModel):
    question: str
    mode: str = "explain"
    k: int = 8
    course: str | None = None
    week: str | None = None
    kind: str | None = None
    model: str | None = None


class AskResponse(BaseModel):
    answer: str
    mode: str
    model: str
    sources: list[Passage]


class DocumentInfo(BaseModel):
    doc_key: str
    title: str
    kind: str
    course: str
    week: str
    tags: str
    n_pages: int
    n_chunks: int
    added_at: str


def _passage(hit: Hit) -> Passage:
    return Passage(
        chunk_id=hit.chunk_id, title=hit.title, citation=hit.citation(),
        section=hit.section, page_start=hit.page_start, page_end=hit.page_end,
        kind=hit.kind, course=hit.course, week=str(hit.week),
        score=round(hit.score, 6), text=hit.text,
    )


@router.get("/documents", response_model=list[DocumentInfo])
def list_documents():
    with _store() as store:
        return [
            DocumentInfo(
                doc_key=r["doc_key"], title=r["title"], kind=r["kind"],
                course=r["course"], week=str(r["week"]), tags=r["tags"],
                n_pages=r["n_pages"], n_chunks=r["n_chunks"], added_at=r["added_at"],
            )
            for r in store.list_documents()
        ]


@router.get("/stats")
def stats():
    with _store() as store:
        return store.stats()


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=1),
    k: int = Query(8, ge=1, le=50),
    course: str | None = None,
    week: str | None = None,
    kind: str | None = None,
):
    with _store() as store:
        hits = Retriever(store).search(q, k=k, filters=Filters(course, week, kind))
        return SearchResponse(query=q, passages=[_passage(h) for h in hits])


@router.post("/ask", response_model=AskResponse)
def ask_question(body: AskRequest):
    if body.mode not in MODES:
        raise HTTPException(400, f"mode must be one of: {', '.join(MODES)}")
    with _store() as store:
        try:
            answer = ask(
                Retriever(store), body.question, mode=body.mode, k=body.k,
                filters=Filters(body.course, body.week, body.kind), model=body.model,
            )
        except MissingAPIKey as exc:
            raise HTTPException(503, str(exc))
        except RuntimeError as exc:
            raise HTTPException(502, str(exc))
        return AskResponse(
            answer=answer.text, mode=answer.mode, model=answer.model,
            sources=[_passage(h) for h in answer.hits],
        )


@router.post("/documents", response_model=DocumentInfo)
async def upload_document(
    file: UploadFile = File(...),
    course: str = Form(""),
    week: str | None = Form(None),
    kind: str | None = Form(None),
    tags: str = Form(""),
):
    name = Path(file.filename or "upload")
    if name.suffix.lower() not in SUPPORTED:
        raise HTTPException(
            400, f"Unsupported file type '{name.suffix}'. Supported: {', '.join(sorted(SUPPORTED))}"
        )

    # Stage the upload on disk so the extractors can seek through it.
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / name.name
        with staged.open("wb") as out:
            shutil.copyfileobj(file.file, out)
        with _store() as store:
            result = ingest_file(
                store, staged, course=course, week=week, kind=kind, tags=tags, force=True
            )
            if result.status == "failed":
                raise HTTPException(400, result.detail)
            row = store.get_document(result.doc_key)
            return DocumentInfo(
                doc_key=row["doc_key"], title=row["title"], kind=row["kind"],
                course=row["course"], week=str(row["week"]), tags=row["tags"],
                n_pages=row["n_pages"], n_chunks=result.n_chunks, added_at=row["added_at"],
            )


@router.delete("/documents/{doc_key}")
def delete_document(doc_key: str):
    with _store() as store:
        if not store.delete_document(doc_key):
            raise HTTPException(404, f"No document keyed '{doc_key}'")
    return {"ok": True, "deleted": doc_key}
