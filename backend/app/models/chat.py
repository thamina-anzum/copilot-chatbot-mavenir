from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    specification: str
    section: str
    page: int
    supporting_chunk_id: str
    excerpt: str | None = None


class ChatMessageRequest(BaseModel):
    query: str = Field(min_length=1, max_length=4000)
    conversation_id: str | None = None


class ChatMessageResponse(BaseModel):
    conversation_id: str
    answer: str
    status: Literal["grounded", "abstained", "error"]
    evidence_strength: Literal["high", "medium", "low"]
    citations: list[Citation] = Field(default_factory=list)
    retrieved_chunks: list[dict] = Field(default_factory=list)
    classification: str | None = None
    latency_ms: int = 0
    evidence_reasoning: str | None = None


class ConversationSummary(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationDetail(BaseModel):
    id: str
    title: str
    messages: list[dict]
