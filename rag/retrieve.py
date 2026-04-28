"""Hybrid retrieval for the CS-website RAG layer.

Combines three signals:
  1. Exact-match boost  – course codes, professor names, program names, page titles
  2. BM25 keyword search  (rank_bm25)
  3. Dense vector similarity  (sentence-transformers embeddings, cosine via dot)

Usage
-----
from rag.retrieve import Retriever
r = Retriever()
results = r.retrieve("What are the prerequisites for CS310?", top_k=5)
for hit in results:
    print(hit["score"], hit["title"], hit["url"])
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

REPO_ROOT = Path(__file__).resolve().parents[1]
INDEX_DIR = REPO_ROOT / "rag" / "index"
CHUNKS_FILE = INDEX_DIR / "chunks.json"
EMBEDDINGS_FILE = INDEX_DIR / "embeddings.npy"
IDS_FILE = INDEX_DIR / "chunk_ids.json"

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Score weights for rank fusion
EXACT_BOOST = 5.0   # additive bonus when query mentions id/title exactly
BM25_WEIGHT = 1.0
VEC_WEIGHT = 2.0


def _tokenize(text: str) -> list[str]:
    """Lower-case, remove punctuation, split."""
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return [t for t in text.split() if len(t) > 1]


def _normalize_course_code(value: str) -> str:
    return re.sub(r"\s+", "", value.upper())


class Retriever:
    def __init__(self) -> None:
        if not CHUNKS_FILE.exists():
            raise FileNotFoundError(
                f"{CHUNKS_FILE} not found – run `python3 rag/build_chunks.py` first."
            )
        if not EMBEDDINGS_FILE.exists():
            raise FileNotFoundError(
                f"{EMBEDDINGS_FILE} not found – run `python3 rag/build_embeddings.py` first."
            )

        self.chunks: list[dict[str, Any]] = json.loads(
            CHUNKS_FILE.read_text(encoding="utf-8")
        )
        self.embeddings: np.ndarray = np.load(EMBEDDINGS_FILE)  # (N, 384) float32
        chunk_ids: list[str] = json.loads(IDS_FILE.read_text(encoding="utf-8"))

        # Build id → row index map
        self._id_to_row: dict[str, int] = {cid: i for i, cid in enumerate(chunk_ids)}
        # Build id → chunk map
        self._id_to_chunk: dict[str, dict] = {c["id"]: c for c in self.chunks}

        # BM25 corpus
        corpus_tokens = [_tokenize(c["text"]) for c in self.chunks]
        self._bm25 = BM25Okapi(corpus_tokens)

        # Exact-match index: maps normalised token → list of chunk ids
        self._exact_index: dict[str, list[str]] = {}
        for chunk in self.chunks:
            keys = self._exact_keys(chunk)
            for key in keys:
                self._exact_index.setdefault(key, []).append(chunk["id"])

        # Lazy-load sentence-transformer (only needed when embeddings exist)
        self._model: SentenceTransformer | None = None

    def _load_model(self) -> SentenceTransformer:
        if self._model is None:
            self._model = SentenceTransformer(MODEL_NAME)
        return self._model

    @staticmethod
    def _exact_keys(chunk: dict[str, Any]) -> list[str]:
        """Return the normalised strings we want to match exactly."""
        keys: list[str] = []
        etype = chunk.get("entity_type", "")

        if etype == "course":
            code = chunk.get("course_code") or ""
            if code:
                keys.append(_normalize_course_code(code))

        name = chunk.get("title") or ""
        if name:
            keys.append(name.lower().strip())

        for kw in chunk.get("keywords") or []:
            if kw:
                keys.append(kw.lower().strip())

        return keys

    def _exact_scores(self, query: str) -> dict[str, float]:
        """Return per-chunk additive score for exact matches."""
        query_norm = query.upper().replace(" ", "")  # for course codes
        query_lower = query.lower()

        scores: dict[str, float] = {}

        for key, cids in self._exact_index.items():
            # Course code pattern: CS310, CS410, etc.
            key_upper = key.upper().replace(" ", "")
            if key_upper and key_upper in query_norm:
                for cid in cids:
                    scores[cid] = scores.get(cid, 0.0) + EXACT_BOOST
                continue

            # Substring match for names/titles/keywords
            if len(key) >= 4 and key in query_lower:
                for cid in cids:
                    scores[cid] = scores.get(cid, 0.0) + EXACT_BOOST

        return scores

    def _bm25_scores(self, query: str) -> list[tuple[str, float]]:
        tokens = _tokenize(query)
        if not tokens:
            return []
        raw = self._bm25.get_scores(tokens)
        max_score = float(raw.max()) if raw.max() > 0 else 1.0
        normed = raw / max_score
        return [(self.chunks[i]["id"], float(normed[i])) for i in range(len(self.chunks))]

    def _vector_scores(self, query: str) -> list[tuple[str, float]]:
        model = self._load_model()
        q_emb = model.encode(
            [query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )[0].astype(np.float32)  # (384,)

        # Cosine similarity = dot product (embeddings are pre-normalised)
        sims = self.embeddings @ q_emb  # (N,)
        return [(self.chunks[i]["id"], float(sims[i])) for i in range(len(self.chunks))]

    def retrieve(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Return top_k chunks as dicts with an added 'score' key."""
        # 1. Exact match
        exact = self._exact_scores(query)

        # 2. BM25
        bm25_raw = dict(self._bm25_scores(query))

        # 3. Vector
        vec_raw = dict(self._vector_scores(query))

        # Merge all chunk ids
        all_ids = set(exact) | set(bm25_raw) | set(vec_raw)

        scored: list[tuple[str, float]] = []
        for cid in all_ids:
            score = (
                exact.get(cid, 0.0)
                + BM25_WEIGHT * bm25_raw.get(cid, 0.0)
                + VEC_WEIGHT * vec_raw.get(cid, 0.0)
            )
            scored.append((cid, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        top = scored[:top_k]

        results: list[dict[str, Any]] = []
        for cid, score in top:
            chunk = dict(self._id_to_chunk.get(cid, {}))
            chunk["score"] = round(score, 4)
            results.append(chunk)

        return results
