from unittest.mock import patch

from app.rag.nodes.classify_query import _heuristic
from app.rag.nodes.evidence_gate import assess_evidence
from app.rag.prompts import ABSTAIN_TEXT


def test_heuristic_out_of_domain():
    assert _heuristic("What is Ericsson's stock price?") == "OUT_OF_DOMAIN"


def test_heuristic_in_domain():
    assert _heuristic("What is the role of the AMF over N2?") == "IN_DOMAIN"


def test_low_scores_are_insufficient():
    assessment = assess_evidence([0.12, 0.10, 0.08])
    assert assessment.sufficient is False
    assert assessment.strength == "low"


def test_high_scores_are_sufficient():
    assessment = assess_evidence([0.82, 0.71, 0.60, 0.40])
    assert assessment.sufficient is True
    assert assessment.strength == "high"


def test_graph_ood_does_not_call_generate():
    from app.rag.graph import build_graph

    graph = build_graph()
    with patch("app.rag.nodes.classify_query.generate_text") as classify_llm, patch(
        "app.rag.nodes.generate.generate_text"
    ) as gen_llm:
        classify_llm.return_value = (
            '{"classification":"OUT_OF_DOMAIN","reason":"stock price","standalone_query":'
            '"What is Ericsson stock price?"}'
        )
        state = graph.invoke(
            {
                "query": "What is Ericsson's stock price?",
                "conversation_history": [],
                "regenerate_attempted": False,
                "node_timings": {},
            }
        )
        gen_llm.assert_not_called()
        assert state["status"] == "abstained"
        assert state["answer"] == ABSTAIN_TEXT


def test_graph_low_evidence_skips_generate():
    from app.models.retrieval import RetrievalResult
    from app.rag.graph import build_graph

    weak = RetrievalResult(
        chunk_id="c1",
        text="unrelated filler about annex numbering conventions",
        chunk_type="prose",
        specification="23.501",
        release="18",
        version="18.10.0",
        section="1",
        section_title="Scope",
        parent_section="",
        page=23,
        source_filename="x.pdf",
        rrf_score=0.01,
        rerank_score=0.05,
    )
    graph = build_graph()
    with patch("app.rag.nodes.classify_query.generate_text") as classify_llm, patch(
        "app.rag.nodes.retrieve.hybrid_search", return_value=[weak]
    ), patch("app.rag.nodes.rerank.rerank_candidates", return_value=[weak]), patch(
        "app.rag.nodes.generate.generate_text"
    ) as gen_llm:
        classify_llm.return_value = (
            '{"classification":"IN_DOMAIN","reason":"5g","standalone_query":"AMF CPU clock"}'
        )
        state = graph.invoke(
            {
                "query": "What is the mandatory AMF CPU clock speed specified by 3GPP?",
                "conversation_history": [],
                "regenerate_attempted": False,
                "node_timings": {},
            }
        )
        gen_llm.assert_not_called()
        assert state["status"] == "abstained"
        assert state["answer"] == ABSTAIN_TEXT
