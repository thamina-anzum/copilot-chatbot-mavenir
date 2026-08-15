"""Async MongoDB Atlas client. Optional — chat still works without persistence."""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: AsyncIOMotorClient | None = None
_disabled = False


def disable_mongo(reason: str = "") -> None:
    global _client, _disabled
    if not _disabled:
        logger.warning(
            "MongoDB disabled for this process; using local fallback. %s "
            "Check Atlas Network Access (allow your IP or 0.0.0.0/0) and the URI.",
            reason,
        )
    _disabled = True
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None


def get_client() -> AsyncIOMotorClient | None:
    global _client
    settings = get_settings()
    if _disabled or not settings.mongodb_configured:
        return None
    if _client is None:
        kwargs: dict = {
            "serverSelectionTimeoutMS": 4000,
            "connectTimeoutMS": 4000,
            "tls": True,
        }
        try:
            import certifi

            kwargs["tlsCAFile"] = certifi.where()
        except ImportError:
            pass
        _client = AsyncIOMotorClient(settings.mongodb_uri, **kwargs)
    return _client


def get_db() -> AsyncIOMotorDatabase | None:
    client = get_client()
    if client is None:
        return None
    return client[get_settings().mongodb_db_name]


async def mongodb_healthy() -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        await client.admin.command("ping")
        return True
    except Exception as exc:  # noqa: BLE001
        disable_mongo(str(exc))
        return False


async def close_mongo() -> None:
    global _client
    if _client is not None:
        _client.close()
        _client = None
