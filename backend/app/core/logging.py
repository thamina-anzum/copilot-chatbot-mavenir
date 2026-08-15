"""Structured logging with secret redaction."""

from __future__ import annotations

import logging
import re
import sys

_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(mongodb(?:\+srv)?://)([^:\s]+):([^@\s]+)@", re.I),
    re.compile(r"(api[_-]?key\s*[=:]\s*)\S+", re.I),
    re.compile(r"(authorization:\s*bearer\s+)\S+", re.I),
    re.compile(r"(sk-[A-Za-z0-9]{8,})"),
    re.compile(r"(AIza[0-9A-Za-z\-_]{20,})"),
    re.compile(r"(gsk_[A-Za-z0-9]{8,})"),
)


def redact(text: str) -> str:
    redacted = text
    redacted = _SECRET_PATTERNS[0].sub(r"\1***:***@", redacted)
    for pattern in _SECRET_PATTERNS[1:]:
        redacted = pattern.sub(lambda m: (m.group(1) if m.lastindex else "") + "***", redacted)
        if pattern.groups == 0:
            redacted = pattern.sub("***", redacted)
    return redacted


class RedactingFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: v if isinstance(v, (int, float)) and not isinstance(v, bool) else redact(str(v))
                    for k, v in record.args.items()
                }
            else:
                cleaned = []
                for a in record.args:
                    if isinstance(a, (int, float)) and not isinstance(a, bool):
                        cleaned.append(a)
                    else:
                        cleaned.append(redact(str(a)))
                record.args = tuple(cleaned)
        return True


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    handler.addFilter(RedactingFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sentence_transformers").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
