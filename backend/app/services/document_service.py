"""Ingested document metadata."""

from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.database.repositories import conversations as repo


def _fallback_docs() -> list[dict]:
    path = Path(get_settings().processed_dir) / "documents.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


async def list_ingested_documents() -> list[dict]:
    try:
        docs = await repo.list_documents()
    except Exception:
        docs = []
    if docs:
        return [
            {
                "specification": d.get("specification"),
                "title": d.get("title"),
                "release": d.get("release"),
                "version": d.get("version"),
                "source_filename": d.get("source_filename"),
                "page_count": d.get("page_count"),
                "chunk_count": d.get("chunk_count"),
            }
            for d in docs
        ]
    return _fallback_docs()
