"""Conversation and message persistence (MongoDB Atlas, with in-memory fallback)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.core.logging import get_logger
from app.database.mongodb import disable_mongo, get_db

logger = get_logger(__name__)

_mem_convos: dict[str, dict[str, Any]] = {}
_mem_msgs: dict[str, list[dict[str, Any]]] = {}
_mem_docs: dict[str, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _mongo_call(op_name: str, coro, fallback):
    try:
        return await coro
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s failed (%s); falling back locally", op_name, exc)
        disable_mongo(str(exc))
        return fallback() if callable(fallback) else fallback


async def create_conversation(title: str) -> dict[str, Any]:
    doc = {
        "_id": str(uuid4()),
        "title": title[:120],
        "created_at": _now(),
        "updated_at": _now(),
    }

    def _local() -> dict[str, Any]:
        _mem_convos[doc["_id"]] = doc
        _mem_msgs[doc["_id"]] = []
        return doc

    db = get_db()
    if db is None:
        return _local()

    async def _insert():
        await db.conversations.insert_one(doc)
        return doc

    return await _mongo_call("create_conversation", _insert(), _local)


async def get_conversation(conversation_id: str) -> dict[str, Any] | None:
    db = get_db()
    if db is None:
        return _mem_convos.get(conversation_id)
    found = await _mongo_call(
        "get_conversation",
        db.conversations.find_one({"_id": conversation_id}),
        lambda: _mem_convos.get(conversation_id),
    )
    return found


async def list_conversations(limit: int = 50) -> list[dict[str, Any]]:
    db = get_db()
    if db is None:
        return list(_mem_convos.values())[:limit]
    return await _mongo_call(
        "list_conversations",
        db.conversations.find().sort("updated_at", -1).limit(limit).to_list(length=limit),
        lambda: list(_mem_convos.values())[:limit],
    )


async def add_message(conversation_id: str, role: str, payload: dict[str, Any]) -> dict[str, Any]:
    doc = {
        "_id": str(uuid4()),
        "conversation_id": conversation_id,
        "role": role,
        "created_at": _now(),
        **payload,
    }

    def _local() -> dict[str, Any]:
        _mem_msgs.setdefault(conversation_id, []).append(doc)
        if conversation_id in _mem_convos:
            _mem_convos[conversation_id]["updated_at"] = _now()
        return doc

    db = get_db()
    if db is None:
        return _local()

    async def _write():
        await db.messages.insert_one(doc)
        await db.conversations.update_one(
            {"_id": conversation_id},
            {"$set": {"updated_at": _now()}},
        )
        return doc

    return await _mongo_call("add_message", _write(), _local)


async def get_messages(conversation_id: str, limit: int = 40) -> list[dict[str, Any]]:
    db = get_db()
    if db is None:
        return (_mem_msgs.get(conversation_id) or [])[:limit]
    return await _mongo_call(
        "get_messages",
        db.messages.find({"conversation_id": conversation_id}).sort("created_at", 1).limit(limit).to_list(length=limit),
        lambda: (_mem_msgs.get(conversation_id) or [])[:limit],
    )


async def upsert_document_meta(meta: dict[str, Any]) -> None:
    db = get_db()
    if db is None:
        _mem_docs[meta["specification"]] = meta
        return
    await _mongo_call(
        "upsert_document_meta",
        db.documents.update_one(
            {"specification": meta["specification"]},
            {"$set": {**meta, "updated_at": _now()}},
            upsert=True,
        ),
        lambda: _mem_docs.__setitem__(meta["specification"], meta),
    )


async def list_documents() -> list[dict[str, Any]]:
    db = get_db()
    if db is None:
        return list(_mem_docs.values())
    return await _mongo_call(
        "list_documents",
        db.documents.find().to_list(length=100),
        lambda: list(_mem_docs.values()),
    )
