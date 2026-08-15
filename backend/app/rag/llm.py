"""Provider-agnostic LLM interface. Gemini primary, Groq as final fallback."""

from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_groq import ChatGroq

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Try the configured model first, then other Gemini IDs, then Groq.
# gemini-2.5-flash has a larger free-tier daily quota; some new keys return 404.
_GEMINI_FALLBACKS = (
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
)


class LLMError(RuntimeError):
    pass


def _clean_key(value: str) -> str:
    return (value or "").strip().strip('"').strip("'")


def _key_configured(value: str) -> bool:
    v = _clean_key(value)
    return bool(v) and "REPLACE_ME" not in v


def _gemini_models() -> list[str]:
    settings = get_settings()
    ordered: list[str] = []
    for name in (settings.gemini_model, *_GEMINI_FALLBACKS):
        if name and name not in ordered:
            ordered.append(name)
    return ordered


def _gemini(model: str):
    settings = get_settings()
    key = _clean_key(settings.google_api_key)
    if not _key_configured(key):
        return None
    return ChatGoogleGenerativeAI(
        model=model,
        google_api_key=key,
        temperature=0.0,
        max_retries=0,
    )


def _groq():
    settings = get_settings()
    key = _clean_key(settings.groq_api_key)
    if not _key_configured(key):
        logger.warning(
            "Groq skipped: GROQ_API_KEY is missing or still REPLACE_ME. "
            "Set it in the repo-root .env to enable llama-3.3-70b-versatile as fallback."
        )
        return None
    return ChatGroq(
        model=settings.groq_model,
        api_key=key,
        groq_api_key=key,
        temperature=0.0,
        max_retries=0,
    )


def generate_text(system: str, user: str, *, json_mode: bool = False) -> str:
    """Gemini variants first; Groq is the last resort after 429/404/other failures."""
    settings = get_settings()
    messages = [SystemMessage(content=system), HumanMessage(content=user)]
    last_error: Exception | None = None

    attempts: list[tuple[str, object]] = []
    groq_llm = _groq()
    gemini_first = settings.llm_provider.lower() != "groq"

    def _add_gemini() -> None:
        for model in _gemini_models():
            llm = _gemini(model)
            if llm is not None:
                attempts.append((f"gemini:{model}", llm))

    if gemini_first:
        _add_gemini()
        if groq_llm is not None:
            attempts.append(("groq:llama-3.3-70b-versatile", groq_llm))
    else:
        if groq_llm is not None:
            attempts.append(("groq:llama-3.3-70b-versatile", groq_llm))
        _add_gemini()

    if not attempts:
        raise LLMError("No LLM provider configured. Set GOOGLE_API_KEY and/or GROQ_API_KEY.")

    for name, llm in attempts:
        try:
            result = llm.invoke(messages)
            text = result.content if isinstance(result.content, str) else str(result.content)
            if not text.strip():
                raise LLMError(f"{name} returned empty content")
            logger.info("LLM response from %s (%s chars)", name, len(text))
            return text
        except Exception as exc:  # noqa: BLE001 — fallback is the point
            logger.warning("LLM provider %s failed: %s", name, exc)
            last_error = exc
            err = str(exc).lower()
            if "429" in err or "quota" in err or "resource exhausted" in err:
                logger.warning("Quota/429 from %s — trying next provider (Groq is last).", name)
    raise LLMError(f"All LLM providers failed: {last_error}")
