from fastapi import APIRouter

from app.database.mongodb import mongodb_healthy
from app.retrieval.vector_store import collection_count, qdrant_healthy

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    mongo_ok = await mongodb_healthy()
    qdrant_ok = qdrant_healthy()
    status = "ok" if qdrant_ok else "degraded"
    return {
        "status": status,
        "qdrant": {"ok": qdrant_ok, "points": collection_count()},
        "mongodb": {"ok": mongo_ok},
    }
