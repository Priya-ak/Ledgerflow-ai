"""Structured logging + request-id middleware. Never logs bodies, tokens or secrets.

Third-party libraries (httpx, h11, drivers) sometimes put credentials into exception messages,
e.g. ``Illegal header value b'Bearer sb_secret_...'``. Every handler is therefore wrapped in a
formatter that masks known secret formats and the exact values of configured secrets.
"""
from __future__ import annotations

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.config import settings

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"sb_(secret|publishable)_[A-Za-z0-9_\-]+"), r"sb_\1_[REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]*"), "[REDACTED_JWT]"),
    (re.compile(r"(?i)\b(Bearer|Basic)\s+[A-Za-z0-9._~+/=\-]+"), r"\1 [REDACTED]"),
    (re.compile(r"(?i)\b(api[-_]?key|apikey|authorization|password|passwd|secret|token)(['\"]?\s*[:=]\s*['\"]?)[^\s'\",;&]+"),
     r"\1\2[REDACTED]"),
    (re.compile(r"(?i)(\w+(?:\+\w+)?://[^:/\s@]+:)[^@\s/]+@"), r"\1[REDACTED]@"),
]
_SECRET_FIELDS = ("JWT_SECRET", "SECRET_KEY", "ENCRYPTION_KEY", "BACKUP_ENCRYPTION_KEY", "SUPABASE_SERVICE_ROLE_KEY",
                  "SUPABASE_ANON_KEY", "BREVO_API_KEY", "GEMINI_API_KEY", "SMTP_PASSWORD")


def _secret_values() -> list[str]:
    vals = [getattr(settings, f, "") for f in _SECRET_FIELDS]
    # Longest first so a secret that contains another is masked completely.
    return sorted({v for v in vals if isinstance(v, str) and len(v) >= 8}, key=len, reverse=True)


def redact(text: str) -> str:
    for value in _secret_values():
        text = text.replace(value, "[REDACTED]")
    for pattern, repl in _PATTERNS:
        text = pattern.sub(repl, text)
    return text


class RedactingFormatter(logging.Formatter):
    """Wraps another formatter (keeps uvicorn's own style) and masks secrets in the final text."""

    def __init__(self, inner: logging.Formatter | None = None) -> None:
        super().__init__()
        self.inner = inner or logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        return redact(self.inner.format(record))


def install_redaction() -> None:
    for name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "ledgerflow"):
        for handler in logging.getLogger(name).handlers:
            if not isinstance(handler.formatter, RedactingFormatter):
                handler.setFormatter(RedactingFormatter(handler.formatter))


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    install_redaction()


access_log = logging.getLogger("ledgerflow.access")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("x-request-id")
        try:
            rid = str(uuid.UUID(rid)) if rid else str(uuid.uuid4())
        except ValueError:
            rid = str(uuid.uuid4())
        request.state.request_id = rid
        start = time.perf_counter()
        response = await call_next(request)
        ms = int((time.perf_counter() - start) * 1000)
        response.headers["x-request-id"] = rid
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["referrer-policy"] = "strict-origin-when-cross-origin"
        access_log.info("method=%s path=%s status=%s ms=%s rid=%s user=%s", request.method,
                        request.url.path, response.status_code, ms, rid, getattr(request.state, "user_id", "-"))
        return response
