from app.rag.citations import citation_from_chunk, resolve_chunk_ids
from app.rag.nodes.verify import _structural_verify


def _chunk(**kwargs):
    base = {
        "chunk_id": "abc",
        "specification": "23.501",
        "section": "6.2.1",
        "section_title": "AMF",
        "page": 521,
        "text": "The AMF includes registration management and terminates N2.",
    }
    base.update(kwargs)
    return base


def test_citation_labels_come_only_from_chunk_metadata():
    chunk = _chunk()
    cite = citation_from_chunk(chunk)
    assert cite.specification == "23.501"
    assert cite.section == "6.2.1"
    assert cite.page == 521
    assert cite.supporting_chunk_id == "abc"
    assert "registration management" in (cite.excerpt or "")


def test_unknown_chunk_id_is_rejected():
    citations, unknown = resolve_chunk_ids(["nope", "abc"], [_chunk()])
    assert unknown == ["nope"]
    assert len(citations) == 1
    assert citations[0].section == "6.2.1"


def test_llm_spec_section_page_are_ignored():
    valid, failures = _structural_verify(
        [
            {
                "specification": "38.300",
                "section": "4.1",
                "page": 25,
                "supporting_chunk_id": "abc",
            }
        ],
        [_chunk()],
    )
    assert not failures
    assert valid[0]["specification"] == "23.501"
    assert valid[0]["section"] == "6.2.1"
    assert valid[0]["page"] == 521
    assert "registration management" in valid[0]["excerpt"]


def test_hallucinated_chunk_id_fails_verify():
    valid, failures = _structural_verify(
        [{"supporting_chunk_id": "invented-id"}],
        [_chunk()],
    )
    assert valid == []
    assert failures
