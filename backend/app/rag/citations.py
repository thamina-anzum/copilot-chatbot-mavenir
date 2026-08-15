"""Citations are built only from retrieved chunk metadata, never from LLM text."""

from __future__ import annotations

from app.models.chat import Citation


def chunk_index(chunks: list[dict]) -> dict[str, dict]:
    return {str(c.get("chunk_id")): c for c in chunks if c.get("chunk_id")}


def citation_from_chunk(chunk: dict) -> Citation:
    """The only constructor for a public citation label."""
    return Citation(
        specification=str(chunk.get("specification") or ""),
        section=str(chunk.get("section") or ""),
        page=int(chunk.get("page") or 0),
        supporting_chunk_id=str(chunk.get("chunk_id") or ""),
        excerpt=(chunk.get("text") or "")[:800],
    )


def resolve_chunk_ids(
    chunk_ids: list[str],
    chunks: list[dict],
) -> tuple[list[Citation], list[str]]:
    """Look up each id. Unknown ids are hallucinated references."""
    by_id = chunk_index(chunks)
    citations: list[Citation] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for raw in chunk_ids:
        cid = str(raw or "").strip()
        if not cid or cid in seen:
            continue
        seen.add(cid)
        chunk = by_id.get(cid)
        if chunk is None:
            unknown.append(cid)
            continue
        citations.append(citation_from_chunk(chunk))
    return citations, unknown
