"""Where the library lives and which models it talks to."""

from __future__ import annotations

import os
from pathlib import Path

# Repo root, so the library sits beside the rest of the project's data.
ROOT = Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    return Path(os.environ.get("RAG_DATA_DIR") or (ROOT / "data" / "rag"))


def db_path() -> Path:
    return Path(os.environ.get("RAG_DB") or (data_dir() / "library.db"))


def library_dir() -> Path:
    """Ingested source files are copied here so the library is self-contained."""
    return Path(os.environ.get("RAG_LIBRARY") or (data_dir() / "sources"))


def answer_model() -> str:
    return os.environ.get("RAG_MODEL") or "claude-sonnet-5"


def embedding_backend() -> str:
    return os.environ.get("RAG_EMBEDDINGS") or "hash"
