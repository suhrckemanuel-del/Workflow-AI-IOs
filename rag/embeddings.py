"""Pluggable embedding backends.

The default backend is deliberately dependency-free: it hashes word and
character n-grams into a fixed-width vector. That is *lexical* similarity with
fuzzy matching — it forgives morphology and typos ("Pigouvian" vs "Pigovian")
that exact BM25 misses — but it is not semantic. Set RAG_EMBEDDINGS=voyage (or
sentence-transformers) for true semantic vectors when a key or GPU is around.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import urllib.request
from typing import Protocol

_WORD = re.compile(r"[a-z0-9]+")

try:  # optional accelerator; everything works without it
    import numpy as _np
except ImportError:  # pragma: no cover
    _np = None


class Embedder(Protocol):
    name: str
    dim: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


class HashingEmbedder:
    """Hashed n-gram vectors. Deterministic, offline, no model download."""

    name = "hash"

    def __init__(self, dim: int = 768):
        self.dim = dim

    def _features(self, text: str) -> dict[int, float]:
        words = _tokens(text)
        counts: dict[int, float] = {}

        def bump(feature: str, weight: float) -> None:
            slot = int.from_bytes(
                hashlib.blake2b(feature.encode(), digest_size=8).digest(), "little"
            ) % self.dim
            counts[slot] = counts.get(slot, 0.0) + weight

        for w in words:
            bump(w, 1.0)
            # Character 4-grams give partial credit for related word forms.
            padded = f"^{w}$"
            for i in range(len(padded) - 3):
                bump(padded[i:i + 4], 0.35)
        for a, b in zip(words, words[1:]):
            bump(f"{a}_{b}", 0.7)
        return counts

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            vec = [0.0] * self.dim
            for slot, count in self._features(text).items():
                # log1p keeps fractional n-gram weights positive; plain log would
                # drive sub-1.0 weights negative and cancel out real overlap.
                vec[slot] = math.log1p(count)
            norm = math.sqrt(sum(v * v for v in vec)) or 1.0
            out.append([v / norm for v in vec])
        return out


class VoyageEmbedder:
    """Voyage AI embeddings — Anthropic's recommended embedding provider."""

    name = "voyage"

    def __init__(self, model: str = "voyage-3", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.environ.get("VOYAGE_API_KEY", "")
        if not self.api_key:
            raise RuntimeError("VOYAGE_API_KEY is not set")
        self.dim = 1024

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), 96):  # stay inside the per-request limit
            batch = texts[i:i + 96]
            payload = json.dumps({"input": batch, "model": self.model}).encode()
            request = urllib.request.Request(
                "https://api.voyageai.com/v1/embeddings",
                data=payload,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                body = json.loads(response.read())
            out.extend(item["embedding"] for item in body["data"])
        if out:
            self.dim = len(out[0])
        return out


class SentenceTransformerEmbedder:
    """Local semantic embeddings when sentence-transformers is installed."""

    name = "sentence-transformers"

    def __init__(self, model: str = "sentence-transformers/all-MiniLM-L6-v2"):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model)
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, normalize_embeddings=True)
        return [list(map(float, v)) for v in vectors]


def get_embedder(backend: str | None = None) -> Embedder | None:
    """Resolve a backend by name, falling back to hashing when unavailable."""
    backend = (backend or os.environ.get("RAG_EMBEDDINGS") or "hash").strip().lower()
    if backend in {"none", "off", "0"}:
        return None
    if backend == "voyage":
        return VoyageEmbedder()
    if backend in {"st", "sentence-transformers", "local"}:
        return SentenceTransformerEmbedder()
    if backend != "hash":
        raise ValueError(f"Unknown embedding backend '{backend}'")
    return HashingEmbedder()


def cosine(a, b) -> float:
    """Cosine similarity of two equal-length vectors (assumes non-zero norms)."""
    if _np is not None:
        va, vb = _np.asarray(a, dtype="f4"), _np.asarray(b, dtype="f4")
        denom = float(_np.linalg.norm(va) * _np.linalg.norm(vb)) or 1.0
        return float(va @ vb) / denom
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1.0
    nb = math.sqrt(sum(y * y for y in b)) or 1.0
    return dot / (na * nb)
