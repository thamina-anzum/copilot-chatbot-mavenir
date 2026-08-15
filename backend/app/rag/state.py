"""LangGraph workflow state."""

from __future__ import annotations

from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    query: str
    standalone_query: str
    conversation_history: list[dict[str, str]]
    classification: str
    classification_reason: str
    retrieved_chunks: list[dict[str, Any]]
    reranked_chunks: list[dict[str, Any]]
    evidence_assessment: dict[str, Any]
    answer: str
    citations: list[dict[str, Any]]
    claims: list[dict[str, Any]]
    hallucinated_chunk_ids: list[str]
    verification_result: dict[str, Any]
    status: str
    evidence_strength: str
    node_timings: dict[str, float]
    regenerate_attempted: bool
    error: str
