"""Deterministic LangGraph state machine for the 3GPP copilot."""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.core.logging import get_logger
from app.rag.nodes.classify_query import classify_query
from app.rag.nodes.evidence_gate import evidence_gate
from app.rag.nodes.finalize import abstain_from_classification, finalize
from app.rag.nodes.generate import generate
from app.rag.nodes.rerank import rerank
from app.rag.nodes.retrieve import retrieve
from app.rag.nodes.verify import verify
from app.rag.state import GraphState

logger = get_logger(__name__)


def _after_classify(state: GraphState) -> str:
    if state.get("classification") == "OUT_OF_DOMAIN":
        return "abstain"
    return "retrieve"


def _after_gate(state: GraphState) -> str:
    assessment = state.get("evidence_assessment") or {}
    if assessment.get("sufficient"):
        return "generate"
    return "finalize"


def _after_verify(state: GraphState) -> str:
    if state.get("status") == "needs_regenerate" and state.get("regenerate_attempted"):
        return "generate"
    return "finalize"


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("classify_query", classify_query)
    graph.add_node("retrieve", retrieve)
    graph.add_node("rerank", rerank)
    graph.add_node("evidence_gate", evidence_gate)
    graph.add_node("generate", generate)
    graph.add_node("verify", verify)
    graph.add_node("finalize", finalize)
    graph.add_node("abstain", abstain_from_classification)

    graph.add_edge(START, "classify_query")
    graph.add_conditional_edges(
        "classify_query",
        _after_classify,
        {"retrieve": "retrieve", "abstain": "abstain"},
    )
    graph.add_edge("retrieve", "rerank")
    graph.add_edge("rerank", "evidence_gate")
    graph.add_conditional_edges(
        "evidence_gate",
        _after_gate,
        {"generate": "generate", "finalize": "finalize"},
    )
    graph.add_edge("generate", "verify")
    graph.add_conditional_edges(
        "verify",
        _after_verify,
        {"generate": "generate", "finalize": "finalize"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("abstain", END)
    return graph.compile()


_app = None


def get_graph():
    global _app
    if _app is None:
        _app = build_graph()
    return _app


def run_graph(query: str, conversation_history: list[dict] | None = None) -> GraphState:
    app = get_graph()
    initial: GraphState = {
        "query": query,
        "standalone_query": query,
        "conversation_history": conversation_history or [],
        "regenerate_attempted": False,
        "node_timings": {},
        "status": "abstained",
        "citations": [],
        "claims": [],
        "hallucinated_chunk_ids": [],
        "retrieved_chunks": [],
        "reranked_chunks": [],
    }
    logger.info("Invoking graph for query=%r", query[:120])
    return app.invoke(initial)
