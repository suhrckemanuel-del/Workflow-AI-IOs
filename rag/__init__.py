"""A small retrieval-augmented library for studying course material.

Ingest lecture slides, problem sets and notes; search them with hybrid
keyword + vector retrieval; ask questions that are answered only from what the
material actually says, with citations back to page or slide.
"""

from rag.answer import Answer, ask
from rag.ingest import ingest_file, ingest_paths
from rag.retriever import Filters, Retriever
from rag.store import Hit, Store

__all__ = [
    "Answer", "ask", "ingest_file", "ingest_paths",
    "Filters", "Retriever", "Hit", "Store",
]
__version__ = "1.0.0"
