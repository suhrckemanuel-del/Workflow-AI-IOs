"""SQLite-backed store: documents, chunks, a BM25 index, and vectors.

Uses SQLite's built-in FTS5 module for keyword search, so the whole retrieval
layer runs on the standard library — no service to start, and the library is a
single file you can copy between machines.
"""

from __future__ import annotations

import array
import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = 1

_SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY,
    doc_key     TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    source_path TEXT NOT NULL,
    kind        TEXT NOT NULL DEFAULT 'material',
    course      TEXT NOT NULL DEFAULT '',
    week        TEXT NOT NULL DEFAULT '',
    tags        TEXT NOT NULL DEFAULT '',
    sha256      TEXT NOT NULL,
    page_label  TEXT NOT NULL DEFAULT 'page',
    n_pages     INTEGER NOT NULL DEFAULT 0,
    added_at    TEXT NOT NULL,
    meta_json   TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS chunks (
    id         INTEGER PRIMARY KEY,
    doc_id     INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    ord        INTEGER NOT NULL,
    text       TEXT NOT NULL,
    section    TEXT NOT NULL DEFAULT '',
    page_start INTEGER NOT NULL DEFAULT 0,
    page_end   INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(doc_id);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    text, section,
    content='chunks', content_rowid='id',
    tokenize='porter unicode61'
);

CREATE TABLE IF NOT EXISTS embeddings (
    chunk_id INTEGER PRIMARY KEY REFERENCES chunks(id) ON DELETE CASCADE,
    backend  TEXT NOT NULL,
    dim      INTEGER NOT NULL,
    vec      BLOB NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
"""

# Keep the FTS index in step with the chunks table.
_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, text, section) VALUES (new.id, new.text, new.section);
END;
CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, section)
    VALUES ('delete', old.id, old.text, old.section);
END;
CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, text, section)
    VALUES ('delete', old.id, old.text, old.section);
    INSERT INTO chunks_fts(rowid, text, section) VALUES (new.id, new.text, new.section);
END;
"""


@dataclass
class Hit:
    chunk_id: int
    doc_id: int
    text: str
    section: str
    page_start: int
    page_end: int
    title: str
    page_label: str
    kind: str
    course: str
    week: str
    score: float = 0.0

    def citation(self) -> str:
        """Human-readable source reference, e.g. 'Lecture 2 — slide 14 — Roadmap'."""
        parts = [self.title]
        if self.page_start:
            if self.page_end and self.page_end != self.page_start:
                parts.append(f"{self.page_label}s {self.page_start}-{self.page_end}")
            else:
                parts.append(f"{self.page_label} {self.page_start}")
        if self.section:
            parts.append(self.section)
        return " — ".join(parts)


def pack_vector(values: Iterable[float]) -> bytes:
    return array.array("f", values).tobytes()


def unpack_vector(blob: bytes) -> array.array:
    out = array.array("f")
    out.frombytes(blob)
    return out


class Store:
    """Thin wrapper over the SQLite library file."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def _migrate(self) -> None:
        self.conn.executescript(_SCHEMA)
        self.conn.executescript(_TRIGGERS)
        self.conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    # ---------------------------------------------------------------- documents

    def get_document(self, doc_key: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM documents WHERE doc_key = ?", (doc_key,)
        ).fetchone()

    def find_by_sha(self, sha256: str) -> sqlite3.Row | None:
        return self.conn.execute(
            "SELECT * FROM documents WHERE sha256 = ?", (sha256,)
        ).fetchone()

    def upsert_document(self, **fields) -> int:
        """Replace a document and all of its chunks."""
        self.delete_document(fields["doc_key"])
        cur = self.conn.execute(
            """INSERT INTO documents
               (doc_key, title, source_path, kind, course, week, tags,
                sha256, page_label, n_pages, added_at, meta_json)
               VALUES (:doc_key, :title, :source_path, :kind, :course, :week, :tags,
                       :sha256, :page_label, :n_pages, :added_at, :meta_json)""",
            {"meta_json": json.dumps(fields.pop("meta", {})), **fields},
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def delete_document(self, doc_key: str) -> bool:
        row = self.get_document(doc_key)
        if row is None:
            return False
        self.conn.execute("DELETE FROM documents WHERE id = ?", (row["id"],))
        self.conn.commit()
        return True

    def list_documents(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT d.*, (SELECT COUNT(*) FROM chunks c WHERE c.doc_id = d.id) AS n_chunks
               FROM documents d ORDER BY d.course, d.week, d.title"""
        ).fetchall()

    # ------------------------------------------------------------------- chunks

    def add_chunks(self, doc_id: int, chunks) -> list[int]:
        ids: list[int] = []
        for i, ch in enumerate(chunks):
            cur = self.conn.execute(
                """INSERT INTO chunks (doc_id, ord, text, section, page_start, page_end)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (doc_id, i, ch.text, ch.section, ch.page_start, ch.page_end),
            )
            ids.append(int(cur.lastrowid))
        self.conn.commit()
        return ids

    def add_embeddings(self, rows: list[tuple[int, str, int, bytes]]) -> None:
        self.conn.executemany(
            "INSERT OR REPLACE INTO embeddings (chunk_id, backend, dim, vec) VALUES (?,?,?,?)",
            rows,
        )
        self.conn.commit()

    def iter_embeddings(self, backend: str):
        return self.conn.execute(
            "SELECT chunk_id, vec FROM embeddings WHERE backend = ?", (backend,)
        )

    def chunks_without_embeddings(self, backend: str) -> list[sqlite3.Row]:
        return self.conn.execute(
            """SELECT c.id, c.text FROM chunks c
               LEFT JOIN embeddings e ON e.chunk_id = c.id AND e.backend = ?
               WHERE e.chunk_id IS NULL""",
            (backend,),
        ).fetchall()

    _HIT_COLUMNS = """c.id, c.doc_id, c.text, c.section, c.page_start, c.page_end,
                      d.title, d.page_label, d.kind, d.course, d.week"""

    def hydrate(self, chunk_ids: list[int]) -> dict[int, Hit]:
        if not chunk_ids:
            return {}
        marks = ",".join("?" * len(chunk_ids))
        rows = self.conn.execute(
            f"""SELECT {self._HIT_COLUMNS} FROM chunks c
                JOIN documents d ON d.id = c.doc_id
                WHERE c.id IN ({marks})""",
            chunk_ids,
        ).fetchall()
        return {r["id"]: Hit(chunk_id=r["id"], **{k: r[k] for k in r.keys() if k != "id"})
                for r in rows}

    def keyword_search(self, fts_query: str, limit: int) -> list[tuple[int, float]]:
        """BM25 search. Returns (chunk_id, score) with higher score = better."""
        try:
            rows = self.conn.execute(
                """SELECT c.id AS id, bm25(chunks_fts, 4.0, 2.0) AS rank
                   FROM chunks_fts
                   JOIN chunks c ON c.id = chunks_fts.rowid
                   WHERE chunks_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (fts_query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            return []  # malformed FTS expression -> no keyword hits
        # bm25() returns negative numbers where more negative is better.
        return [(r["id"], -float(r["rank"])) for r in rows]

    def stats(self) -> dict:
        one = lambda sql: int(self.conn.execute(sql).fetchone()[0])
        return {
            "documents": one("SELECT COUNT(*) FROM documents"),
            "chunks": one("SELECT COUNT(*) FROM chunks"),
            "embeddings": one("SELECT COUNT(*) FROM embeddings"),
            "characters": one("SELECT COALESCE(SUM(LENGTH(text)), 0) FROM chunks"),
            "path": str(self.path),
        }

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
