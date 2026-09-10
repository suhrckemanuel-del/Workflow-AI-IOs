"""Command line for the course library.

    python -m rag add <files...> --course "Applied Micro" --week 2
    python -m rag ask "why is a Pigouvian tax equal to marginal damage?"
    python -m rag quiz "externalities" --week 2
    python -m rag search "Coase" --k 5
    python -m rag list | stats | remove <doc-key>
"""

from __future__ import annotations

import argparse
import sys
import textwrap
from pathlib import Path

from rag import config
from rag.answer import MODES, MissingAPIKey, ask
from rag.ingest import ingest_paths
from rag.retriever import Filters, Retriever
from rag.store import Store


def _store() -> Store:
    return Store(config.db_path())


def _filters(args) -> Filters:
    return Filters(
        course=getattr(args, "course", None),
        week=getattr(args, "week", None),
        kind=getattr(args, "kind", None),
    )


def cmd_add(args) -> int:
    with _store() as store:
        report = ingest_paths(
            store,
            [Path(p) for p in args.paths],
            course=args.course or "",
            week=args.week,
            kind=args.kind,
            tags=args.tags or "",
            force=args.force,
            backend=args.embeddings,
        )
    for result in report.results:
        mark = {"added": "+", "updated": "~", "skipped": "=", "failed": "!"}[result.status]
        line = f" {mark} {result.title}"
        if result.n_chunks:
            line += f"  ({result.n_chunks} chunks, {result.n_pages} pages)"
        if result.detail:
            line += f"  — {result.detail}"
        print(line)
    print(f"\n{report.added} document(s) indexed, {report.chunks} chunks total.")
    return 1 if report.failed else 0


def cmd_search(args) -> int:
    with _store() as store:
        hits = Retriever(store, args.embeddings).search(args.query, k=args.k, filters=_filters(args))
    if not hits:
        print("No matches. Try different wording, or check `python -m rag list`.")
        return 1
    for i, hit in enumerate(hits, start=1):
        print(f"\n[{i}] {hit.citation()}   (score {hit.score:.4f})")
        body = hit.text if args.full else textwrap.shorten(hit.text, 400, placeholder=" …")
        print(textwrap.indent(body, "    "))
    return 0


def _run_answer(args, mode: str, question: str) -> int:
    with _store() as store:
        retriever = Retriever(store, args.embeddings)
        try:
            answer = ask(
                retriever, question, mode=mode, k=args.k,
                filters=_filters(args), model=args.model,
            )
        except MissingAPIKey as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    print(answer.text)
    if answer.hits:
        print("\nSources")
        for source in answer.sources():
            print(f"  {source}")
    return 0


def cmd_ask(args) -> int:
    return _run_answer(args, args.mode, args.question)


def cmd_quiz(args) -> int:
    topic = args.topic or "the material in this library"
    return _run_answer(args, "quiz", f"Give me {args.n} practice questions on {topic}.")


def cmd_list(args) -> int:
    with _store() as store:
        rows = store.list_documents()
    if not rows:
        print("Library is empty. Add material with `python -m rag add <files>`.")
        return 0
    print(f"{'KEY':38} {'KIND':10} {'WK':4} {'CHUNKS':>6}  TITLE")
    for row in rows:
        print(f"{row['doc_key'][:38]:38} {row['kind'][:10]:10} "
              f"{str(row['week'])[:4]:4} {row['n_chunks']:>6}  {row['title']}")
    return 0


def cmd_stats(args) -> int:
    with _store() as store:
        for key, value in store.stats().items():
            print(f"{key:12} {value}")
    return 0


def cmd_remove(args) -> int:
    with _store() as store:
        ok = store.delete_document(args.doc_key)
    print(f"Removed {args.doc_key}." if ok else f"No document keyed '{args.doc_key}'.")
    return 0 if ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="rag", description="Personal RAG library for course material."
    )
    subs = parser.add_subparsers(dest="command", required=True)

    def shared(sub, retrieval: bool = True) -> None:
        sub.add_argument("--course", help="filter/label by course name")
        sub.add_argument("--week", help="filter/label by week or topic number")
        sub.add_argument("--kind", help="lecture | exercises | notes")
        sub.add_argument("--embeddings", help="hash | voyage | sentence-transformers | none")
        if retrieval:
            sub.add_argument("-k", type=int, default=8, help="passages to retrieve")

    add = subs.add_parser("add", help="ingest files or folders")
    add.add_argument("paths", nargs="+")
    add.add_argument("--tags", help="comma-separated tags")
    add.add_argument("--force", action="store_true", help="reindex even if unchanged")
    shared(add, retrieval=False)
    add.set_defaults(func=cmd_add)

    search = subs.add_parser("search", help="show matching passages, no model call")
    search.add_argument("query")
    search.add_argument("--full", action="store_true", help="print whole passages")
    shared(search)
    search.set_defaults(func=cmd_search)

    ask_p = subs.add_parser("ask", help="ask a question about the material")
    ask_p.add_argument("question")
    ask_p.add_argument("--mode", choices=MODES, default="explain")
    ask_p.add_argument("--model", help=f"default: {config.answer_model()}")
    shared(ask_p)
    ask_p.set_defaults(func=cmd_ask)

    quiz = subs.add_parser("quiz", help="generate practice questions")
    quiz.add_argument("topic", nargs="?")
    quiz.add_argument("-n", type=int, default=5, help="number of questions")
    quiz.add_argument("--model")
    shared(quiz)
    quiz.set_defaults(func=cmd_quiz)

    listing = subs.add_parser("list", help="list indexed documents")
    listing.set_defaults(func=cmd_list)

    stats = subs.add_parser("stats", help="library size and location")
    stats.set_defaults(func=cmd_stats)

    remove = subs.add_parser("remove", help="delete a document from the library")
    remove.add_argument("doc_key")
    remove.set_defaults(func=cmd_remove)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
