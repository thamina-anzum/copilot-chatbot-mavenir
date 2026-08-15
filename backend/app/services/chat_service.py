"""Chat orchestration: history → graph → persist."""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.logging import get_logger
from app.database.repositories import conversations as repo
from app.models.chat import ChatMessageResponse, Citation
from app.observability.langfuse import trace_graph_run
from app.rag.citations import citation_from_chunk, chunk_index
from app.rag.graph import run_graph
from app.rag.prompts import ABSTAIN_TEXT

logger = get_logger(__name__)


def _history_for_graph(messages: list[dict]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for m in messages:
        role = m.get("role")
        if role == "user":
            out.append({"role": "user", "content": m.get("content") or m.get("query") or ""})
        elif role == "assistant":
            out.append({"role": "assistant", "content": m.get("answer") or m.get("content") or ""})
    return out[-8:]


async def send_message(query: str, conversation_id: str | None = None) -> ChatMessageResponse:
    started = time.perf_counter()
    if conversation_id:
        convo = await repo.get_conversation(conversation_id)
        if convo is None:
            convo = await repo.create_conversation(query)
            conversation_id = convo["_id"]
    else:
        convo = await repo.create_conversation(query)
        conversation_id = convo["_id"]

    prior = await repo.get_messages(conversation_id)
    history = _history_for_graph(prior)
    await repo.add_message(conversation_id, "user", {"content": query, "query": query})

    with trace_graph_run(query) as trace_holder:
        try:
            result = await asyncio.to_thread(run_graph, query, history)
            trace_holder["result"] = result
        except Exception:
            logger.exception("Graph invocation failed")
            latency = int((time.perf_counter() - started) * 1000)
            response = ChatMessageResponse(
                conversation_id=conversation_id,
                answer="The assistant could not complete this request. Please try again.",
                status="error",
                evidence_strength="low",
                citations=[],
                retrieved_chunks=[],
                latency_ms=latency,
            )
            await repo.add_message(conversation_id, "assistant", response.model_dump())
            return response

    latency = int((time.perf_counter() - started) * 1000)
    timings = result.get("node_timings") or {}
    total_from_nodes = int(sum(timings.values())) if timings else latency

    evidence = result.get("reranked_chunks") or result.get("retrieved_chunks") or []
    by_id = chunk_index(evidence)
    citations: list[Citation] = []
    for c in result.get("citations") or []:
        cid = str(c.get("supporting_chunk_id") or "")
        chunk = by_id.get(cid)
        if chunk is None:
            continue
        citations.append(citation_from_chunk(chunk))

    status = result.get("status") or "abstained"
    if status not in {"grounded", "abstained", "error"}:
        status = "abstained"
    answer = result.get("answer") or ABSTAIN_TEXT
    if status == "abstained":
        answer = ABSTAIN_TEXT
        citations = []

    retrieved = []
    for ch in (result.get("reranked_chunks") or result.get("retrieved_chunks") or [])[:5]:
        retrieved.append(
            {
                "chunk_id": ch.get("chunk_id"),
                "specification": ch.get("specification"),
                "section": ch.get("section"),
                "section_title": ch.get("section_title"),
                "page": ch.get("page"),
                "chunk_type": ch.get("chunk_type"),
                "text": ch.get("text"),
                "rerank_score": ch.get("rerank_score"),
                "rrf_score": ch.get("rrf_score"),
                "vector_score": ch.get("vector_score"),
                "bm25_score": ch.get("bm25_score"),
            }
        )

    response = ChatMessageResponse(
        conversation_id=conversation_id,
        answer=answer,
        status=status,  # type: ignore[arg-type]
        evidence_strength=result.get("evidence_strength") or "low",  # type: ignore[arg-type]
        citations=citations,
        retrieved_chunks=retrieved,
        classification=result.get("classification"),
        latency_ms=latency or total_from_nodes,
        evidence_reasoning=(result.get("evidence_assessment") or {}).get("reasoning"),
    )
    await repo.add_message(
        conversation_id,
        "assistant",
        {
            **response.model_dump(),
            "verification_result": result.get("verification_result"),
            "node_timings": timings,
        },
    )
    return response


async def get_conversation_detail(conversation_id: str) -> dict[str, Any] | None:
    convo = await repo.get_conversation(conversation_id)
    if convo is None:
        return None
    messages = await repo.get_messages(conversation_id)
    return {
        "id": convo["_id"],
        "title": convo.get("title"),
        "messages": [
            {k: v for k, v in m.items() if k != "_id" or True} for m in messages
        ],
    }
