from typing import Literal

from pydantic import BaseModel, Field


class RetrievalResult(BaseModel):
    chunk_id: str
    text: str
    chunk_type: str
    specification: str
    release: str
    version: str
    section: str
    section_title: str
    parent_section: str
    page: int
    source_filename: str
    has_diagram: bool = False
    vector_score: float | None = None
    bm25_score: float | None = None
    rrf_score: float | None = None
    rerank_score: float | None = None


class EvidenceAssessment(BaseModel):
    sufficient: bool
    strength: Literal["high", "medium", "low"]
    reasoning: str
    top_scores: list[float] = Field(default_factory=list)
    chunks_above_secondary: int = 0
    score_spread: float = 0.0
    threshold_used: float = 0.0
