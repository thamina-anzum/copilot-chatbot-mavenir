"""Retrieve hybrid candidates."""

from __future__ import annotations

import time

from app.core.logging import get_logger
from app.rag.state import GraphState
from app.retrieval.hybrid import hybrid_search

logger = get_logger(__name__)


def retrieve(state: GraphState) -> GraphState:
    t0 = time.perf_counter()
    query = state.get("standalone_query") or state["query"]
    results = hybrid_search(query)
    timings = dict(state.get("node_timings") or {})
    timings["retrieve"] = (time.perf_counter() - t0) * 1000
    logger.info("Retrieved %s chunks", len(results))
    return {
        **state,
        "retrieved_chunks": [r.model_dump() for r in results],
        "node_timings": timings,
    }
