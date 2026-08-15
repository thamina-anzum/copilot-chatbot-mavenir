"""Classify IN_DOMAIN / AMBIGUOUS / OUT_OF_DOMAIN and rewrite follow-ups."""

from __future__ import annotations

import json
import re
import time

from app.core.logging import get_logger
from app.rag.llm import LLMError, generate_text
from app.rag.prompts import CLASSIFY_SYSTEM
from app.rag.state import GraphState

logger = get_logger(__name__)

IN_DOMAIN_HINTS = re.compile(
    r"\b(5g|5gs|amf|smf|upf|udm|pcf|ausf|nssf|nrf|nef|smsf|ran|gnodeb|gnb|"
    r"ng-ran|nas|pdu session|registration|handover|qos|s-nssai|nssai|"
    r"23\.501|23\.502|24\.501|38\.300|n1|n2|n3|n4|n6|ue|plmn)\b",
    re.I,
)
OUT_DOMAIN_HINTS = re.compile(
    r"\b(stock price|recipe|bitcoin|weather|movie|football|nba|celebrity)\b",
    re.I,
)

# Common 3GPP acronym typos / near-misses (query rewrite only).
_TYPO_MAP = (
    (re.compile(r"\bamt\b", re.I), "AMF"),
    (re.compile(r"\bsmf\b", re.I), "SMF"),
    (re.compile(r"\bupf\b", re.I), "UPF"),
)


def normalize_query(query: str) -> str:
    out = query
    for pattern, repl in _TYPO_MAP:
        out = pattern.sub(repl, out)
    return out


def _heuristic(query: str) -> str:
    if OUT_DOMAIN_HINTS.search(query) and not IN_DOMAIN_HINTS.search(query):
        return "OUT_OF_DOMAIN"
    if IN_DOMAIN_HINTS.search(query):
        return "IN_DOMAIN"
    return "AMBIGUOUS"


def classify_query(state: GraphState) -> GraphState:
    t0 = time.perf_counter()
    query = normalize_query(state["query"])
    history = state.get("conversation_history") or []
    history_blob = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in history[-8:])
    user = f"Conversation history:\n{history_blob or '(none)'}\n\nCurrent query:\n{query}"
    classification = _heuristic(query)
    reason = "heuristic fallback"
    standalone = query
    try:
        raw = generate_text(CLASSIFY_SYSTEM, user, json_mode=True)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I | re.S)
        data = json.loads(raw)
        classification = str(data.get("classification", classification)).upper()
        if classification not in {"IN_DOMAIN", "OUT_OF_DOMAIN", "AMBIGUOUS"}:
            classification = _heuristic(query)
        reason = str(data.get("reason") or reason)
        standalone = normalize_query(str(data.get("standalone_query") or query).strip() or query)
    except (LLMError, json.JSONDecodeError, TypeError) as exc:
        logger.warning("Classification LLM failed (%s); using heuristic %s", exc, classification)

    timings = dict(state.get("node_timings") or {})
    timings["classify_query"] = (time.perf_counter() - t0) * 1000
    logger.info("Classified %r as %s", query[:80], classification)
    return {
        **state,
        "classification": classification,
        "classification_reason": reason,
        "standalone_query": standalone,
        "node_timings": timings,
    }
