"""Hybrid retrieval: vector + BM25 merged with Reciprocal Rank Fusion."""

from __future__ import annotations

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.retrieval import RetrievalResult

logger = get_logger(__name__)


def reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievalResult]],
    k: int = 60,
) -> list[RetrievalResult]:
    """Merge ranked lists with Reciprocal Rank Fusion.

    RRF score for a document d is sum over lists i of 1 / (k + rank_i(d)),
    where rank is 1-based. k=60 is the constant from Cormack et al. (2009)
    and is the standard default used in hybrid search literature.
    """
    by_id: dict[str, RetrievalResult] = {}
    scores: dict[str, float] = {}
    for results in ranked_lists:
        for rank, item in enumerate(results, start=1):
            cid = item.chunk_id
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            if cid not in by_id:
                by_id[cid] = item
            else:
                existing = by_id[cid]
                if item.vector_score is not None:
                    existing.vector_score = item.vector_score
                if item.bm25_score is not None:
                    existing.bm25_score = item.bm25_score
    merged = []
    for cid, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        item = by_id[cid]
        item.rrf_score = score
        merged.append(item)
    return merged


def hybrid_search(
    query: str,
    vector_top_k: int | None = None,
    bm25_top_k: int | None = None,
    limit: int | None = None,
) -> list[RetrievalResult]:
    settings = get_settings()
    vector_top_k = vector_top_k or settings.vector_top_k
    bm25_top_k = bm25_top_k or settings.bm25_top_k
    limit = limit or settings.hybrid_candidates

    from app.retrieval.bm25 import get_bm25_index
    from app.retrieval.embeddings import embed_query
    from app.retrieval.vector_store import search as vector_search

    query_vec = embed_query(query)
    vector_hits = vector_search(query_vec, top_k=vector_top_k)
    bm25_hits = get_bm25_index().search(query, top_k=bm25_top_k)
    merged = reciprocal_rank_fusion([vector_hits, bm25_hits], k=settings.rrf_k)
    logger.info(
        "Hybrid search: vector=%s bm25=%s merged=%s query=%r",
        len(vector_hits),
        len(bm25_hits),
        len(merged[:limit]),
        query[:80],
    )
    return merged[:limit]
