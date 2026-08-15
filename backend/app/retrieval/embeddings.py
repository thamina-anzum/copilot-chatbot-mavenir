"""sentence-transformers wrapper for BAAI/bge-large-en-v1.5."""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


@lru_cache
def get_embedding_model():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    logger.info("Loading embedding model %s", settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def embedding_dimension() -> int:
    return int(get_embedding_model().get_sentence_embedding_dimension())


def batch_embed(texts: list[str], batch_size: int = 32) -> list[list[float]]:
    if not texts:
        return []
    model = get_embedding_model()
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        normalize_embeddings=True,
    )
    return [v.tolist() for v in vectors]


def embed_query(query: str) -> list[float]:
    model = get_embedding_model()
    prefixed = BGE_QUERY_PREFIX + query
    vector = model.encode(prefixed, normalize_embeddings=True)
    return vector.tolist()
