"""Optional Langfuse tracing. App must run if credentials are unset."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
_warned = False
_client = None


def _client_or_none():
    global _client, _warned
    settings = get_settings()
    if not settings.langfuse_enabled:
        if not _warned:
            logger.warning("Langfuse unconfigured — tracing disabled, app continues normally")
            _warned = True
        return None
    if _client is None:
        try:
            from langfuse import Langfuse

            _client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Langfuse init failed: %s", exc)
            return None
    return _client


@contextmanager
def trace_graph_run(query: str) -> Iterator[dict[str, Any]]:
    holder: dict[str, Any] = {"result": None, "trace": None}
    client = _client_or_none()
    if client is None:
        yield holder
        return
    try:
        holder["trace"] = client.trace(name="3gpp-rag", input={"query": query})
        yield holder
    except Exception as exc:  # noqa: BLE001
        logger.warning("Langfuse trace error: %s", exc)
        yield holder
    finally:
        try:
            result = holder.get("result")
            trace = holder.get("trace")
            if trace is not None and result is not None:
                timings = result.get("node_timings") or {}
                for node, ms in timings.items():
                    trace.span(name=node, output={"latency_ms": ms})
                trace.update(
                    output={
                        "status": result.get("status"),
                        "classification": result.get("classification"),
                        "evidence": result.get("evidence_assessment"),
                        "citations": result.get("citations"),
                        "verification": result.get("verification_result"),
                        "answer": result.get("answer"),
                    }
                )
            if client is not None:
                client.flush()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Langfuse flush failed: %s", exc)
