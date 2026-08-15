"""Grounded generation from reranked evidence only."""

from __future__ import annotations

import json
import re
import time

from pydantic import BaseModel, Field, ValidationError

from app.core.logging import get_logger
from app.rag.citations import resolve_chunk_ids
from app.rag.llm import LLMError, generate_text
from app.rag.prompts import ABSTAIN_TEXT, GENERATE_SYSTEM
from app.rag.state import GraphState

logger = get_logger(__name__)


class ClaimRef(BaseModel):
    claim: str
    chunk_ids: list[str] = Field(default_factory=list)


class GenerationOut(BaseModel):
    answer: str
    claims: list[ClaimRef] = Field(default_factory=list)


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            return json.loads(match.group(0))
        raise


def _evidence_block(chunks: list[dict]) -> str:
    allowed = ", ".join(str(c.get("chunk_id")) for c in chunks)
    parts = [f"Allowed chunk_ids (use ONLY these): {allowed}\n"]
    for c in chunks:
        parts.append(
            f"[CHUNK_ID: {c.get('chunk_id')}]\n"
            f"{c.get('text')}\n"
        )
    return "\n".join(parts)


def generate(state: GraphState) -> GraphState:
    t0 = time.perf_counter()
    query = state.get("standalone_query") or state["query"]
    chunks = state.get("reranked_chunks") or []
    timings = dict(state.get("node_timings") or {})
    if not chunks:
        timings["generate"] = (time.perf_counter() - t0) * 1000
        return {
            **state,
            "answer": ABSTAIN_TEXT,
            "citations": [],
            "claims": [],
            "status": "abstained",
            "node_timings": timings,
        }

    user = (
        f"Question:\n{query}\n\n"
        f"Evidence (use ONLY this):\n{_evidence_block(chunks)}\n\n"
        "Respond with JSON. Do not output specification, section, or page fields."
    )
    parsed: GenerationOut | None = None
    last_err: str | None = None
    for attempt in range(2):
        try:
            raw = generate_text(GENERATE_SYSTEM, user, json_mode=True)
            parsed = GenerationOut.model_validate(_parse_json(raw))
            break
        except (LLMError, ValidationError, json.JSONDecodeError) as exc:
            last_err = str(exc)
            logger.warning("Generate parse/LLM failure attempt %s: %s", attempt + 1, exc)

    timings["generate"] = (time.perf_counter() - t0) * 1000
    if parsed is None:
        return {
            **state,
            "answer": ABSTAIN_TEXT,
            "citations": [],
            "claims": [],
            "status": "abstained",
            "error": f"generation_failed: {last_err}",
            "node_timings": timings,
        }

    requested_ids: list[str] = []
    for claim in parsed.claims:
        requested_ids.extend(claim.chunk_ids)
    citations, unknown = resolve_chunk_ids(requested_ids, chunks)
    logger.info(
        "Resolved %s citations from chunk_ids; unknown=%s",
        len(citations),
        unknown,
    )
    return {
        **state,
        "answer": parsed.answer,
        "citations": [c.model_dump() for c in citations],
        "claims": [c.model_dump() for c in parsed.claims],
        "hallucinated_chunk_ids": unknown,
        "status": "grounded",
        "node_timings": timings,
    }
