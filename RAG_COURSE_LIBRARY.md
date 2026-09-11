# Course Library (RAG)

A personal retrieval system for study material. Ingest lecture slides, problem
sets and notes; ask questions that are answered **only** from what your own
material says, with citations back to the page or slide.

Built for the Applied Microeconomics / Personnel Economics material in this
repo, but nothing in it is course-specific.

---

## Quick start

```bash
pip install pypdf python-pptx python-docx        # file formats
export ANTHROPIC_API_KEY=sk-ant-...              # only needed for `ask` / `quiz`

python -m rag add ~/Downloads/Lecture_3.pdf --course "Applied Microeconomics"
python -m rag ask  "Why does a Pigouvian tax equal marginal external damage?"
```

## Commands

| Command | What it does |
|---|---|
| `rag add <files/folders>` | Ingest. Folders recurse; unchanged files are skipped. |
| `rag ask "<question>"` | Answer from your material, with citations. |
| `rag quiz [topic] -n 5` | Practice questions with worked answers. |
| `rag search "<query>"` | Show the matching passages. **No model call, no API key.** |
| `rag list` / `rag stats` | What is indexed. |
| `rag remove <doc-key>` | Drop a document. |

### Lecture recordings

Panopto (and Zoom, Teams, Echo360) generate captions for every recording.
Download the caption file and ingest it — the transcript becomes searchable
alongside the slides:

```bash
python -m rag add ~/Downloads/Lecture_3.vtt --course "Applied Micro" --week 3
python -m rag search "Coase theorem" --kind transcript
```

Citations for a transcript are **timestamps**, not page numbers — a hit reads
`Lecture 3 recording — 12:30`, so you can scrub straight to that point in the
video. Cues are pooled into 90-second windows, because a single caption line
is too small to retrieve on its own; repeated rolling-caption lines are
dropped, and speaker tags stripped.

In Panopto: open the recording, then either the **Captions** tab in the left
sidebar (select all, copy into a `.txt`) or **Settings → Downloads →
Download captions** if your lecturer enabled it.

Run any of them as `python -m rag <command>`.

### Modes for `ask`

```bash
python -m rag ask "externalities" --mode cheatsheet   # condensed revision sheet
python -m rag ask "Exercise 2.3"   --mode solve       # exam-style worked solution
python -m rag ask "public goods"   --mode quiz        # questions + answers
python -m rag ask "what is MRS?"   --mode explain     # default
```

### Filters

Every retrieval command takes `--course`, `--week`, and `--kind`
(`lecture` / `exercises` / `transcript`), so you can revise one week at a time:

```bash
python -m rag quiz "externalities" --week 2 --kind exercises
python -m rag search "Coase" --week 2 --full
```

Week and kind are inferred on ingest (`Lecture_2.pptx` → week 2;
`exercises_week_2.pdf` → week 2, kind `exercises`; any `.vtt`/`.srt` → kind
`transcript`). Override with flags.

---

## Adding more material

```bash
python -m rag add ~/Downloads/                   # a whole folder
python -m rag add slides.pdf --week 4 --tags "midterm"
python -m rag add notes.pdf --force              # re-index an edited file
```

Supported: `.pdf`, `.pptx`, `.docx`, `.md`, `.txt`, `.html`, `.csv`,
and `.vtt` / `.srt` (lecture recording captions).
Scanned PDFs need OCR first — the extractor reports that rather than indexing
an empty document. Ingest is keyed by filename, so re-adding a corrected file
replaces the old version instead of duplicating it.

---

## How it works

**Extraction → repair → chunking → hybrid retrieval → grounded answer.**

1. **Extraction** keeps the page or slide number for every block of text, plus
   PowerPoint speaker notes and table cells.

2. **Repair** (`rag/normalize.py`) undoes PDF export damage. LaTeX decks lose
   their ligatures, so "efficient" arrives as `e¢ cient` and "firm" as
   ` rm`; PowerPoint equation export doubles every math glyph (`𝑉𝑉 ln 𝐺𝐺`).
   Left alone, none of those words are searchable. Each mapping was derived by
   inspecting the actual course files. The repair is context-aware: `e¢ cient`
   closes up to *efficient*, while `payo⁄ of` stays *payoff of*.

3. **Chunking** starts a new chunk at every exercise number, so a question is
   never split from its setup, and labels each chunk with a section title —
   which is why citations read `Exercise 2.3` and `Lecture 2 — slide 27`.

4. **Retrieval** fuses two rankings with reciprocal rank fusion: SQLite FTS5
   BM25 (precise on jargon like *Coase*, *Pigouvian*) and vector similarity
   (forgiving of paraphrase and spelling). Results are then diversified with
   MMR so eight passages aren't eight copies of the same slide.

5. **Answering** passes the numbered excerpts to Claude with a prompt that
   forbids using outside knowledge and requires inline `[n]` citations. For
   exam revision a confident wrong answer is worse than "the material does not
   cover this".

The core runs on the Python standard library — SQLite with FTS5, no vector
database and no service to start. The library is a single file you can copy
between machines.

### Embedding backends

| `RAG_EMBEDDINGS` | Behaviour |
|---|---|
| `hash` *(default)* | Hashed word + character n-grams. Offline, no downloads. **Lexical with fuzzy matching, not semantic** — it forgives morphology and spelling (*Pigouvian* / *Pigovian*) but does not understand meaning. |
| `voyage` | True semantic embeddings via Voyage AI. Needs `VOYAGE_API_KEY`. |
| `sentence-transformers` | Local semantic embeddings. Needs the package and a model download. |
| `none` | BM25 keyword search only. |

The default is chosen so the system works with zero setup. If retrieval ever
feels too literal, switch to `voyage` and re-ingest with `--force`.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `RAG_DATA_DIR` | `data/rag` | Where the library and copied sources live |
| `RAG_DB` | `<data>/library.db` | Database path |
| `RAG_MODEL` | `claude-sonnet-5` | Model used for answers |
| `RAG_EMBEDDINGS` | `hash` | Embedding backend |
| `ANTHROPIC_API_KEY` | — | Required for `ask` and `quiz` only |

`data/rag/` is **gitignored**. This repository is public, and lecture slides
and answer keys are your university's copyright — keep them out of it. To move
your library to another machine, copy the `data/rag/` folder.

---

## HTTP API

The routes mount under `/api` on the existing FastAPI app:

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/rag/documents` | List indexed documents |
| `POST` | `/api/rag/documents` | Upload and ingest (multipart) |
| `DELETE` | `/api/rag/documents/{doc_key}` | Remove a document |
| `GET` | `/api/rag/search?q=...&k=8` | Passages, no model call |
| `POST` | `/api/rag/ask` | Grounded answer with sources |
| `GET` | `/api/rag/stats` | Library size |

---

## Tests

```bash
python -m unittest tests.test_rag -v
```

50 tests covering ligature repair, exercise-aware chunking, caption parsing
and timestamp labelling, embedding behaviour, FTS query safety, re-ingest and
deletion, and retrieval filters.
