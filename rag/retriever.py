"""Hybrid retrieval: BM25 keyword search fused with vector similarity.

Neither signal is enough alone. BM25 nails precise jargon ("Coase theorem",
"Pigouvian") but misses paraphrases; vectors catch near-misses but drift on
rare terms. Reciprocal rank fusion combines the two rankings without needing
the two score scales to be comparable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from rag.embeddings import cosine, get_embedder
from rag.store import Hit, Store, unpack_vector

RRF_K = 60          # standard reciprocal-rank-fusion damping constant
POOL_MULTIPLIER = 6  # how many candidates each retriever contributes per final hit

# Floor for rejecting a question the library simply does not cover. Kept
# deliberately loose: measured on real course queries the vector and keyword
# signals overlap with off-topic ones, so a tight gate would suppress genuine
# answers. Only a question with no keyword hits at all *and* weak vector
# similarity is refused outright; borderline cases are passed to the model,
# whose prompt requires it to say when the excerpts do not answer the question.
MIN_VECTOR_SIM = 0.25

_TOKEN = re.compile(r"[A-Za-z0-9']+")

# Dropped from keyword queries: they match everything and rank nothing.
_STOPWORDS = frozenset("""
a about an and are as at be but by can could did do does explain for from
give had has have how i if in into is it its me my of on or please should
so tell than that the their them then there these they this to was we were
what when where which who why will with would you your
""".split())


@dataclass
class Filters:
    course: str | None = None
    week: str | None = None
    kind: str | None = None

    def matches(self, hit: Hit) -> bool:
        if self.course and hit.course.lower() != self.course.lower():
            return False
        if self.week and str(hit.week).lower() != str(self.week).lower():
            return False
        if self.kind and hit.kind.lower() != self.kind.lower():
            return False
        return True


def build_fts_query(question: str) -> str:
    """Turn free text into a safe FTS5 MATCH expression."""
    terms = [t.lower() for t in _TOKEN.findall(question)]
    terms = [t for t in terms if len(t) > 1 and t not in _STOPWORDS]
    if not terms:
        terms = [t.lower() for t in _TOKEN.findall(question)][:8]
    if not terms:
        return ""
    # Quote every term so punctuation and FTS keywords cannot break the syntax.
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(terms))


def _rrf(rankings: list[list[int]], weights: list[float]) -> dict[int, float]:
    scores: dict[int, float] = {}
    for ranking, weight in zip(rankings, weights):
        for position, chunk_id in enumerate(ranking):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + weight / (RRF_K + position + 1)
    return scores


def _mmr(hits: list[Hit], vectors: dict[int, list[float]], k: int, lambda_: float) -> list[Hit]:
    """Maximal marginal relevance: trade a little relevance for less redundancy."""
    if not vectors or len(hits) <= 1:
        return hits[:k]
    selected: list[Hit] = []
    pool = list(hits)
    while pool and len(selected) < k:
        best, best_score = None, -1e9
        for candidate in pool:
            relevance = candidate.score
            redundancy = 0.0
            cv = vectors.get(candidate.chunk_id)
            if cv is not None:
                for chosen in selected:
                    sv = vectors.get(chosen.chunk_id)
                    if sv is not None:
                        redundancy = max(redundancy, cosine(cv, sv))
            score = lambda_ * relevance - (1 - lambda_) * redundancy
            if score > best_score:
                best, best_score = candidate, score
        selected.append(best)
        pool.remove(best)
    return selected


class Retriever:
    def __init__(self, store: Store, backend: str | None = None):
        self.store = store
        self.embedder = get_embedder(backend)

    def _vector_ranking(
        self, question: str, limit: int
    ) -> tuple[list[int], dict[int, list[float]], float]:
        """Return (ranked ids, vectors by id, best similarity seen)."""
        if self.embedder is None:
            return [], {}, 0.0
        query_vec = self.embedder.embed([question])[0]
        scored: list[tuple[float, int]] = []
        vectors: dict[int, list[float]] = {}
        for row in self.store.iter_embeddings(self.embedder.name):
            vec = unpack_vector(row["vec"])
            vectors[row["chunk_id"]] = vec
            scored.append((cosine(query_vec, vec), row["chunk_id"]))
        scored.sort(reverse=True)
        best = scored[0][0] if scored else 0.0
        return [cid for _, cid in scored[:limit]], vectors, best

    def search(
        self,
        question: str,
        k: int = 8,
        filters: Filters | None = None,
        diversify: bool = True,
        lambda_: float = 0.7,
    ) -> list[Hit]:
        """Return the k best chunks for `question`, most relevant first."""
        if not question.strip():
            return []
        filters = filters or Filters()
        pool = max(k * POOL_MULTIPLIER, 30)

        keyword = self.store.keyword_search(build_fts_query(question), pool)
        keyword_ids = [cid for cid, _ in keyword]
        vector_ids, vectors, best_sim = self._vector_ranking(question, pool)

        # Nothing in the library is even lexically close: refuse rather than
        # hand the model a pile of unrelated passages to reason from.
        if not keyword_ids and best_sim < MIN_VECTOR_SIM:
            return []

        # Keyword search is the stronger signal on technical vocabulary, so it
        # carries more weight in the fusion.
        fused = _rrf([keyword_ids, vector_ids], [1.0, 0.7])
        if not fused:
            return []

        hits = self.store.hydrate(list(fused))
        ranked: list[Hit] = []
        for chunk_id, score in sorted(fused.items(), key=lambda kv: kv[1], reverse=True):
            hit = hits.get(chunk_id)
            if hit is None or not filters.matches(hit):
                continue
            hit.score = score
            ranked.append(hit)

        if diversify:
            return _mmr(ranked[: k * 3], vectors, k, lambda_)
        return ranked[:k]
