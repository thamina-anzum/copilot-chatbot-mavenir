"""Terminal node: normalize API-facing fields."""

from __future__ import annotations

import time

from app.rag.prompts import ABSTAIN_TEXT
from app.rag.state import GraphState


def finalize(state: GraphState) -> GraphState:
    t0 = time.perf_counter()
    status = state.get("status") or "abstained"
    if status not in {"grounded", "abstained", "error"}:
        status = "abstained"
    answer = state.get("answer") or ABSTAIN_TEXT
    if status == "abstained":
        answer = ABSTAIN_TEXT
        citations: list = []
    else:
        citations = state.get("citations") or []
    assessment = state.get("evidence_assessment") or {}
    strength = state.get("evidence_strength") or assessment.get("strength") or "low"
    timings = dict(state.get("node_timings") or {})
    timings["finalize"] = (time.perf_counter() - t0) * 1000
    return {
        **state,
        "status": status,
        "answer": answer,
        "citations": citations,
        "evidence_strength": strength,
        "node_timings": timings,
    }


def abstain_from_classification(state: GraphState) -> GraphState:
    timings = dict(state.get("node_timings") or {})
    return finalize(
        {
            **state,
            "answer": ABSTAIN_TEXT,
            "citations": [],
            "status": "abstained",
            "evidence_strength": "low",
            "evidence_assessment": {
                "sufficient": False,
                "strength": "low",
                "reasoning": f"OUT_OF_DOMAIN: {state.get('classification_reason')}",
                "top_scores": [],
            },
            "node_timings": timings,
        }
    )
