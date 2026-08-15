"""Qdrant vector store wrapper."""

from __future__ import annotations

import uuid
from functools import lru_cache
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.document import DocumentChunk
from app.models.retrieval import RetrievalResult

logger = get_logger(__name__)


@lru_cache
def get_qdrant_client() -> QdrantClient:
    settings = get_settings()
    mode = settings.qdrant_mode.lower().strip()
    if mode == "server":
        logger.info("Connecting to Qdrant server %s:%s", settings.qdrant_host, settings.qdrant_port)
        return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, timeout=60)
    path = Path(settings.qdrant_path)
    path.mkdir(parents=True, exist_ok=True)
    logger.info("Using embedded Qdrant at %s", path)
    return QdrantClient(path=str(path))


def create_collection(dimension: int, *, recreate: bool = False) -> None:
    settings = get_settings()
    client = get_qdrant_client()
    name = settings.qdrant_collection
    existing = {c.name for c in client.get_collections().collections}
    if name in existing:
        if recreate:
            client.delete_collection(name)
        else:
            logger.info("Qdrant collection %s already exists", name)
            return
    client.create_collection(
        collection_name=name,
        vectors_config=qmodels.VectorParams(size=dimension, distance=qmodels.Distance.COSINE),
    )
    logger.info("Created Qdrant collection %s dim=%s", name, dimension)


def upsert_chunks(chunks: list[DocumentChunk], vectors: list[list[float]], batch_size: int = 64) -> int:
    if len(chunks) != len(vectors):
        raise ValueError("chunks and vectors length mismatch")
    settings = get_settings()
    client = get_qdrant_client()
    total = 0
    for start in range(0, len(chunks), batch_size):
        batch_chunks = chunks[start : start + batch_size]
        batch_vecs = vectors[start : start + batch_size]
        points = [
            qmodels.PointStruct(
                id=str(uuid.uuid5(uuid.NAMESPACE_URL, ch.chunk_id)),
                vector=vec,
                payload=ch.model_dump(),
            )
            for ch, vec in zip(batch_chunks, batch_vecs, strict=True)
        ]
        client.upsert(collection_name=settings.qdrant_collection, points=points)
        total += len(points)
    logger.info("Upserted %s points into %s", total, settings.qdrant_collection)
    return total


def search(query_vector: list[float], top_k: int | None = None) -> list[RetrievalResult]:
    settings = get_settings()
    top_k = top_k or settings.vector_top_k
    client = get_qdrant_client()
    hits = client.search(
        collection_name=settings.qdrant_collection,
        query_vector=query_vector,
        limit=top_k,
        with_payload=True,
    )
    results: list[RetrievalResult] = []
    for hit in hits:
        payload = hit.payload or {}
        results.append(
            RetrievalResult(
                chunk_id=payload.get("chunk_id", ""),
                text=payload.get("text", ""),
                chunk_type=payload.get("chunk_type", "prose"),
                specification=payload.get("specification", ""),
                release=payload.get("release", ""),
                version=payload.get("version", ""),
                section=payload.get("section", ""),
                section_title=payload.get("section_title", ""),
                parent_section=payload.get("parent_section", ""),
                page=int(payload.get("page") or 0),
                source_filename=payload.get("source_filename", ""),
                has_diagram=bool(payload.get("has_diagram")),
                vector_score=float(hit.score),
            )
        )
    return results


def collection_count() -> int:
    settings = get_settings()
    try:
        client = get_qdrant_client()
        info = client.get_collection(settings.qdrant_collection)
        return int(info.points_count or 0)
    except Exception:
        return -1


def qdrant_healthy() -> bool:
    try:
        get_qdrant_client().get_collections()
        return True
    except Exception:
        return False
