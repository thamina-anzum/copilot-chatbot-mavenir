"""BM25 keyword index with tokenization that keeps spec numbers and acronyms intact."""

from __future__ import annotations

import pickle
import re
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.document import DocumentChunk
from app.models.retrieval import RetrievalResult

logger = get_logger(__name__)

# Keeps 23.501, n2, s-nssai, 5gs, ts-23.501-style tokens together.
TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*", re.I)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN_RE.findall(text)]


class BM25Index:
    def __init__(self, chunks: list[DocumentChunk], tokenized: list[list[str]], engine: BM25Okapi):
        self.chunks = chunks
        self.tokenized = tokenized
        self.engine = engine

    def search(self, query: str, top_k: int | None = None) -> list[RetrievalResult]:
        settings = get_settings()
        top_k = top_k or settings.bm25_top_k
        tokens = tokenize(query)
        if not tokens or not self.chunks:
            return []
        scores = self.engine.get_scores(tokens)
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results: list[RetrievalResult] = []
        for idx, score in ranked:
            if score <= 0:
                continue
            ch = self.chunks[idx]
            results.append(
                RetrievalResult(
                    **ch.model_dump(),
                    bm25_score=float(score),
                )
            )
        return results


def build_index(chunks: list[DocumentChunk]) -> BM25Index:
    tokenized = [tokenize(c.text) for c in chunks]
    engine = BM25Okapi(tokenized)
    logger.info("Built BM25 index over %s chunks", len(chunks))
    return BM25Index(chunks=chunks, tokenized=tokenized, engine=engine)


def persist_index(index: BM25Index, path: Path | None = None) -> Path:
    settings = get_settings()
    path = path or Path(settings.bm25_index_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "chunks": [c.model_dump() for c in index.chunks],
        "tokenized": index.tokenized,
    }
    with path.open("wb") as fh:
        pickle.dump(payload, fh, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Persisted BM25 index to %s", path)
    return path


def load_index(path: Path | None = None) -> BM25Index:
    settings = get_settings()
    path = path or Path(settings.bm25_index_path)
    with path.open("rb") as fh:
        payload = pickle.load(fh)
    chunks = [DocumentChunk(**c) for c in payload["chunks"]]
    tokenized = payload["tokenized"]
    engine = BM25Okapi(tokenized)
    return BM25Index(chunks=chunks, tokenized=tokenized, engine=engine)


_cached: BM25Index | None = None


def get_bm25_index() -> BM25Index:
    global _cached
    if _cached is None:
        _cached = load_index()
    return _cached
