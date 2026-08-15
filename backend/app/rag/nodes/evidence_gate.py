"""Explicit, inspectable evidence gate — not an LLM judgment."""

from __future__ import annotations

import time

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.retrieval import EvidenceAssessment
from app.rag.prompts import ABSTAIN_TEXT
from app.rag.state import GraphState

logger = get_logger(__name__)


def assess_evidence(scores: list[float]) -> EvidenceAssessment:
    settings = get_settings()
    threshold = settings.evidence_threshold
    secondary = settings.evidence_secondary_threshold
    min_chunks = settings.evidence_min_chunks
    top_scores = scores[:5]
    top = top_scores[0] if top_scores else 0.0
    above = sum(1 for s in scores if s >= secondary)
    spread = (max(scores) - min(scores)) if len(scores) > 1 else 0.0
    sufficient = bool(top >= threshold and above >= min_chunks)

    if top >= threshold + 0.15 and above >= 2:
        strength = "high"
    elif sufficient:
        strength = "medium"
    else:
        strength = "low"

    reasoning = (
        f"top_rerank={top:.3f} threshold={threshold:.3f}; "
        f"chunks_above_secondary({secondary:.3f})={above} min={min_chunks}; "
        f"spread={spread:.3f}; decision={'GENERATE' if sufficient else 'ABSTAIN'}"
    )
    logger.info("Evidence gate: %s", reasoning)
    return EvidenceAssessment(
        sufficient=sufficient,
        strength=strength,
        reasoning=reasoning,
        top_scores=[round(s, 4) for s in top_scores],
        chunks_above_secondary=above,
        score_spread=round(spread, 4),
        threshold_used=threshold,
    )


def evidence_gate(state: GraphState) -> GraphState:
    t0 = time.perf_counter()
    chunks = state.get("reranked_chunks") or []
    scores = [float(c.get("rerank_score") or 0.0) for c in chunks]
    assessment = assess_evidence(scores)
    timings = dict(state.get("node_timings") or {})
    timings["evidence_gate"] = (time.perf_counter() - t0) * 1000
    update: GraphState = {
        **state,
        "evidence_assessment": assessment.model_dump(),
        "evidence_strength": assessment.strength,
        "node_timings": timings,
    }
    if not assessment.sufficient:
        update["answer"] = ABSTAIN_TEXT
        update["status"] = "abstained"
        update["citations"] = []
    return update
