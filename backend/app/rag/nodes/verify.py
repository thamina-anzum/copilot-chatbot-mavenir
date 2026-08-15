"""Verify citations against retrieved chunks and claim entailment."""

from __future__ import annotations

import json
import re
import time

from app.core.logging import get_logger
from app.rag.citations import citation_from_chunk, chunk_index, resolve_chunk_ids
from app.rag.llm import LLMError, generate_text
from app.rag.prompts import ABSTAIN_TEXT, VERIFY_SYSTEM
from app.rag.state import GraphState

logger = get_logger(__name__)


def _structural_verify(citations: list[dict], chunks: list[dict]) -> tuple[list[dict], list[str]]:
    """Every citation must resolve by chunk_id to a retrieved chunk.

    Labels are rebuilt from that chunk's stored metadata — LLM spec/section/page
    fields are ignored even if present.
    """
    ids = [str(c.get("supporting_chunk_id") or "") for c in citations]
    resolved, unknown = resolve_chunk_ids(ids, chunks)
    failures = [f"hallucinated chunk_id {cid}" for cid in unknown]
    if not ids:
        failures.append("no supporting chunk_ids")
    return [c.model_dump() for c in resolved], failures


def _entailment_check(answer: str, claims: list[dict], chunks: list[dict]) -> dict:
    by_id = chunk_index(chunks)
    pairs = []
    for claim in claims:
        text = str(claim.get("claim") or "")
        for cid in claim.get("chunk_ids") or []:
            ch = by_id.get(str(cid))
            if ch is None:
                continue
            pairs.append(
                f"CLAIM: {text}\n"
                f"CHUNK_ID: {ch.get('chunk_id')}\n"
                f"PASSAGE:\n{ch.get('text')}"
            )
    if not pairs and answer:
        # Fall back to pairing the full answer with each cited chunk's real text
        for ch in chunks:
            pairs.append(
                f"CLAIM: {answer}\n"
                f"CHUNK_ID: {ch.get('chunk_id')}\n"
                f"PASSAGE:\n{ch.get('text')}"
            )
    user = (
        "For each CLAIM/PASSAGE pair, decide if THAT passage entails the claim.\n\n"
        + "\n---\n".join(pairs)
        + "\n\nReturn JSON."
    )
    try:
        raw = generate_text(VERIFY_SYSTEM, user, json_mode=True)
        if raw.strip().startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw.strip(), flags=re.I | re.S)
        data = json.loads(raw)
        return {
            "all_supported": bool(data.get("all_supported")),
            "claims": data.get("claims") or [],
            "method": "llm_entailment",
        }
    except (LLMError, json.JSONDecodeError) as exc:
        logger.warning("Entailment LLM failed: %s — treating as unsupported", exc)
        return {"all_supported": False, "claims": [], "method": "llm_entailment", "error": str(exc)}


def verify(state: GraphState) -> GraphState:
    t0 = time.perf_counter()
    chunks = state.get("reranked_chunks") or []
    citations = state.get("citations") or []
    claims = state.get("claims") or []
    answer = state.get("answer") or ""
    hallucinated = list(state.get("hallucinated_chunk_ids") or [])

    valid, failures = _structural_verify(citations, chunks)
    failures.extend(f"hallucinated chunk_id {cid}" for cid in hallucinated if cid)

    entailment = {"all_supported": True, "claims": [], "method": "skipped"}
    if valid and answer and state.get("status") == "grounded" and not failures:
        entailment = _entailment_check(answer, claims, chunks)

    # Hard gate: cited chunk_ids must exist in retrieved evidence.
    # Entailment is recorded for explainability; a paraphrase that is still
    # backed by a real chunk must not force abstention.
    ok = bool(valid) and not failures
    # Rebuild labels again from real chunks (defense in depth)
    by_id = chunk_index(chunks)
    rebuilt = []
    for cite in valid:
        ch = by_id.get(str(cite.get("supporting_chunk_id") or ""))
        if ch is not None:
            rebuilt.append(citation_from_chunk(ch).model_dump())
    valid = rebuilt

    result = {
        "ok": ok,
        "structural_failures": failures,
        "valid_citations": valid,
        "entailment": entailment,
    }
    timings = dict(state.get("node_timings") or {})
    timings["verify"] = (time.perf_counter() - t0) * 1000
    logger.info("Verification ok=%s failures=%s", ok, failures)

    update: GraphState = {
        **state,
        "citations": valid,
        "verification_result": result,
        "node_timings": timings,
    }
    if not ok:
        if not state.get("regenerate_attempted"):
            update["regenerate_attempted"] = True
            if valid:
                keep_ids = {c.get("supporting_chunk_id") for c in valid}
                update["reranked_chunks"] = [c for c in chunks if c.get("chunk_id") in keep_ids]
            update["status"] = "needs_regenerate"
            update["hallucinated_chunk_ids"] = []
        else:
            update["answer"] = ABSTAIN_TEXT
            update["citations"] = []
            update["status"] = "abstained"
            update["evidence_strength"] = "low"
    else:
        update["status"] = "grounded"
        update["citations"] = valid
    return update
