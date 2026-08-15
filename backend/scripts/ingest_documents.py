"""Ingest 3GPP PDFs: parse, chunk, embed, upsert Qdrant, persist BM25."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.core.config import get_settings  # noqa: E402
from app.core.logging import configure_logging, get_logger  # noqa: E402
from app.ingestion.chunker import chunk_document  # noqa: E402
from app.ingestion.document_processor import process_document  # noqa: E402
from app.retrieval.bm25 import build_index, persist_index  # noqa: E402
from app.retrieval.embeddings import batch_embed, embedding_dimension  # noqa: E402
from app.retrieval.vector_store import create_collection, upsert_chunks  # noqa: E402

configure_logging()
logger = get_logger("ingest")


def _print_samples(chunks, n: int = 6) -> None:
    print("\n--- sample chunks ---")
    for ch in chunks[:n]:
        preview = ch.text.replace("\n", " ")[:180]
        print(
            f"[{ch.chunk_type}] {ch.specification} §{ch.section} "
            f"({ch.section_title!r}) p.{ch.page}\n  {preview}\n"
        )


def main() -> None:
    settings = get_settings()
    pdf_dir = Path(settings.pdf_dir)
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if not pdfs:
        raise SystemExit(f"No PDFs found in {pdf_dir}")

    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    all_chunks = []
    documents = []

    for pdf in pdfs:
        print(f"\n=== {pdf.name} ===")
        doc = process_document(str(pdf))
        chunks = chunk_document(doc)
        types = Counter(c.chunk_type for c in chunks)
        print(
            f"spec={doc['specification']} rel={doc['release']} v={doc['version']} "
            f"pages={doc['page_count']} chunks={len(chunks)} {dict(types)}"
        )
        _print_samples(chunks)
        all_chunks.extend(chunks)
        documents.append(
            {
                "specification": doc["specification"],
                "title": doc["title"],
                "release": doc["release"],
                "version": doc["version"],
                "source_filename": doc["source_filename"],
                "page_count": doc["page_count"],
                "chunk_count": len(chunks),
            }
        )

    chunks_path = Path(settings.chunks_path)
    chunks_path.write_text(
        json.dumps([c.model_dump() for c in all_chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    docs_path = settings.processed_dir / "documents.json"
    docs_path.write_text(json.dumps(documents, indent=2), encoding="utf-8")
    print(f"\nWrote {len(all_chunks)} chunks -> {chunks_path}")

    embeddable = [
        c
        for c in all_chunks
        if not (
            c.chunk_type == "figure" and len(c.text.strip()) < settings.min_embed_chars
        )
        and len(c.text.strip()) >= settings.min_embed_chars
    ]
    skipped = len(all_chunks) - len(embeddable)
    print(f"Embedding {len(embeddable)} chunks (skipped {skipped} near-empty)")

    dim = embedding_dimension()
    print(f"Embedding dimension = {dim}")
    create_collection(dim, recreate=True)
    vectors = batch_embed([c.text for c in embeddable])
    upserted = upsert_chunks(embeddable, vectors)
    index = build_index(embeddable)
    persist_index(index)

    print("\n=== ingest complete ===")
    print(f"documents: {len(documents)}")
    print(f"chunks total: {len(all_chunks)}")
    print(f"embedded/upserted: {upserted}")
    print(f"bm25: {settings.bm25_index_path}")
    print(f"types: {dict(Counter(c.chunk_type for c in all_chunks))}")


if __name__ == "__main__":
    main()
