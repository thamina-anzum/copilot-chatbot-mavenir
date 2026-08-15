"""Cross-encoder reranker using BAAI/bge-reranker-base."""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.retrieval import RetrievalResult

logger = get_logger(__name__)


@lru_cache
def get_reranker():
    from sentence_transformers import CrossEncoder

    settings = get_settings()
    logger.info("Loading reranker %s", settings.reranker_model)
    return CrossEncoder(settings.reranker_model, max_length=512)


def _sigmoid(xs: list[float]) -> list[float]:
    arr = np.asarray(xs, dtype=np.float64)
    return (1.0 / (1.0 + np.exp(-arr))).tolist()


def rerank(
    query: str,
    candidates: list[RetrievalResult],
    top_k: int | None = None,
) -> list[RetrievalResult]:
    settings = get_settings()
    top_k = top_k or settings.rerank_top_k
    if not candidates:
        return []
    model = get_reranker()
    pairs = [(query, c.text) for c in candidates]
    raw_scores = model.predict(pairs, convert_to_numpy=True).tolist()
    probs = _sigmoid(raw_scores)
    scored = list(zip(candidates, probs, strict=True))
    scored.sort(key=lambda x: x[1], reverse=True)
    out: list[RetrievalResult] = []
    for item, prob in scored[:top_k]:
        item.rerank_score = float(prob)
        out.append(item)
    top_score = 0.0
    if out and out[0].rerank_score is not None:
        top_score = float(out[0].rerank_score)
    logger.info(
        "Reranked %s -> %s; top score=%.3f",
        int(len(candidates)),
        int(len(out)),
        top_score,
    )
    return out
