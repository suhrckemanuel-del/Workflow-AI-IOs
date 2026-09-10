"""Answer questions from retrieved course material using Claude.

Talks to the Messages API over urllib so the library has no hard dependency on
the anthropic SDK; if the SDK is installed it is used instead. Every mode
grounds its output in retrieved chunks and cites them by number, and the
prompts forbid filling gaps from background knowledge — for exam revision, a
confident wrong answer is worse than "the material does not cover this".
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass

from rag import config
from rag.retriever import Filters, Retriever
from rag.store import Hit

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

_BASE_RULES = """You are a tutor helping a university student revise. You are given \
numbered excerpts from that student's own course material.

Rules:
- Ground every claim in the excerpts and cite them inline as [1], [2], ...
- If the excerpts do not answer the question, say so plainly and state what is \
missing. Never invent a definition, formula, or result that is not in them.
- Reproduce notation exactly as the course uses it (for example MPB, MSC, \
w = a + bq). The student is graded on that notation.
- Be concise and concrete. Derivations beat prose.
- The excerpts come from PDFs and slides, so they may be fragmentary. Say when \
an excerpt is too garbled to rely on."""

_MODES = {
    "explain": _BASE_RULES + """

Answer the student's question directly. Where a result follows from a \
derivation, show the steps.""",

    "solve": _BASE_RULES + """

Work through the exercise step by step, as in an exam answer: state what is \
given, set up the maximisation or equilibrium condition, derive the result, \
then interpret it in one or two sentences. If the excerpts contain the \
official answer, solve it yourself first, then check against that answer and \
flag any disagreement.""",

    "quiz": _BASE_RULES + """

Write practice questions on this topic drawn from the excerpts. For each: pose \
the question, leave a blank line, then give the answer under a heading \
"Answer". Mix recall, derivation, and interpretation. Prefer questions in the \
style of the course's own exercises.""",

    "cheatsheet": _BASE_RULES + """

Produce a compact revision sheet: key definitions, the conditions that \
characterise each result, the formulas, and the standard pitfalls. Use short \
bullets and headings, not paragraphs.""",
}


@dataclass
class Answer:
    text: str
    hits: list[Hit]
    model: str
    mode: str

    def sources(self) -> list[str]:
        return [f"[{i}] {h.citation()}" for i, h in enumerate(self.hits, start=1)]


class MissingAPIKey(RuntimeError):
    pass


def format_context(hits: list[Hit]) -> str:
    blocks = []
    for i, hit in enumerate(hits, start=1):
        blocks.append(f"[{i}] {hit.citation()}\n{hit.text}")
    return "\n\n---\n\n".join(blocks)


def call_claude(system: str, user: str, model: str, max_tokens: int = 2000) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise MissingAPIKey(
            "ANTHROPIC_API_KEY is not set. Retrieval still works: "
            "use `python -m rag search` to read the source passages directly."
        )

    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
    }

    try:  # prefer the SDK when it is available
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(**payload)
        return "".join(b.text for b in response.content if b.type == "text")
    except ImportError:
        pass

    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            "x-api-key": api_key,
            "anthropic-version": API_VERSION,
            "content-type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise RuntimeError(f"Anthropic API error {exc.code}: {detail}") from exc
    return "".join(part.get("text", "") for part in body.get("content", []))


def ask(
    retriever: Retriever,
    question: str,
    *,
    mode: str = "explain",
    k: int = 8,
    filters: Filters | None = None,
    model: str | None = None,
    max_tokens: int = 2000,
) -> Answer:
    """Retrieve, then answer. Raises MissingAPIKey if no key is configured."""
    if mode not in _MODES:
        raise ValueError(f"Unknown mode '{mode}'. Choose from: {', '.join(_MODES)}")

    hits = retriever.search(question, k=k, filters=filters)
    model = model or config.answer_model()

    if not hits:
        return Answer(
            text="Nothing in the library matches that. Ingest the relevant "
                 "material first, or try different wording.",
            hits=[], model=model, mode=mode,
        )

    user = (
        f"Course material excerpts:\n\n{format_context(hits)}\n\n"
        f"---\n\nStudent's request: {question}"
    )
    return Answer(call_claude(_MODES[mode], user, model, max_tokens), hits, model, mode)


MODES = tuple(_MODES)
