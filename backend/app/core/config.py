"""Application settings loaded from environment / .env."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    mongodb_uri: str = ""
    mongodb_db_name: str = "3gpp_copilot"

    qdrant_mode: str = "embedded"
    qdrant_path: str = str(REPO_ROOT / "data" / "qdrant")
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "3gpp_chunks"

    llm_provider: str = "gemini"
    google_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    embedding_model: str = "BAAI/bge-small-en-v1.5"
    reranker_model: str = "BAAI/bge-reranker-base"

    vector_top_k: int = 10
    bm25_top_k: int = 10
    hybrid_candidates: int = 20
    rerank_top_k: int = 5
    rrf_k: int = 60

    evidence_threshold: float = 0.42
    evidence_secondary_threshold: float = 0.28
    evidence_min_chunks: int = 1

    chunk_size: int = 1400
    chunk_overlap: int = 180

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    data_dir: Path = REPO_ROOT / "data"
    pdf_dir: Path = REPO_ROOT / "data" / "3gpp"
    processed_dir: Path = REPO_ROOT / "data" / "processed"
    bm25_index_path: Path = REPO_ROOT / "data" / "processed" / "bm25_index.pkl"
    chunks_path: Path = REPO_ROOT / "data" / "processed" / "chunks.json"

    min_embed_chars: int = 20

    @model_validator(mode="after")
    def resolve_relative_paths(self) -> "Settings":
        path_fields = (
            "qdrant_path",
            "data_dir",
            "pdf_dir",
            "processed_dir",
            "bm25_index_path",
            "chunks_path",
        )
        for name in path_fields:
            value = Path(getattr(self, name))
            if not value.is_absolute():
                value = (REPO_ROOT / value).resolve()
            setattr(self, name, value if name != "qdrant_path" else str(value))
        return self

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    @property
    def mongodb_configured(self) -> bool:
        uri = self.mongodb_uri.strip()
        return bool(uri) and "REPLACE_ME" not in uri


@lru_cache
def get_settings() -> Settings:
    return Settings()
