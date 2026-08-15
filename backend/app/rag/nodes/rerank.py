"""Rerank retrieved candidates."""

from __future__ import annotations

import time

from app.core.logging import get_logger
from app.models.retrieval import RetrievalResult
from app.rag.state import GraphState
from app.retrieval.reranker import rerank as rerank_candidates

logger = get_logger(__name__)


def rerank(state: GraphState) -> GraphState:
    t0 = time.perf_counter()
    query = state.get("standalone_query") or state["query"]
    candidates = [RetrievalResult(**c) for c in state.get("retrieved_chunks") or []]
    ranked = rerank_candidates(query, candidates)
    timings = dict(state.get("node_timings") or {})
    timings["rerank"] = (time.perf_counter() - t0) * 1000
    return {
        **state,
        "reranked_chunks": [r.model_dump() for r in ranked],
        "node_timings": timings,
    }
