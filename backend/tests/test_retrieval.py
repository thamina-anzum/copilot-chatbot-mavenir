from app.models.retrieval import RetrievalResult
from app.retrieval.bm25 import tokenize
from app.retrieval.hybrid import reciprocal_rank_fusion


def _hit(cid: str, **scores) -> RetrievalResult:
    return RetrievalResult(
        chunk_id=cid,
        text=f"text-{cid}",
        chunk_type="prose",
        specification="23.501",
        release="18",
        version="18.10.0",
        section="6.2.1",
        section_title="AMF",
        parent_section="6.2",
        page=520,
        source_filename="ts_123501.pdf",
        **scores,
    )


def test_tokenize_keeps_spec_numbers_and_acronyms():
    tokens = tokenize("N2 interface in TS 23.501 and S-NSSAI for 5GS")
    assert "n2" in tokens
    assert "23.501" in tokens
    assert "s-nssai" in tokens
    assert "5gs" in tokens


def test_rrf_deduplicates_by_chunk_id():
    vector = [_hit("a", vector_score=0.9), _hit("b", vector_score=0.8), _hit("c", vector_score=0.7)]
    bm25 = [_hit("b", bm25_score=12.0), _hit("d", bm25_score=11.0), _hit("a", bm25_score=9.0)]
    merged = reciprocal_rank_fusion([vector, bm25], k=60)
    ids = [m.chunk_id for m in merged]
    assert len(ids) == len(set(ids))
    assert set(ids) == {"a", "b", "c", "d"}
    # a and b appear in both lists so they should outrank unique c/d
    assert merged[0].chunk_id in {"a", "b"}
    assert merged[1].chunk_id in {"a", "b"}
    by_id = {m.chunk_id: m for m in merged}
    assert by_id["a"].vector_score == 0.9
    assert by_id["a"].bm25_score == 9.0
    assert by_id["a"].rrf_score is not None


def test_rrf_k_documented_default():
    # k=60: two first-place ranks → 1/61 + 1/61
    vector = [_hit("x", vector_score=1.0)]
    bm25 = [_hit("x", bm25_score=1.0)]
    merged = reciprocal_rank_fusion([vector, bm25], k=60)
    assert abs(merged[0].rrf_score - (1 / 61 + 1 / 61)) < 1e-9
