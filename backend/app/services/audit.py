"""Audit logging helper. Metadata must never contain secrets or passwords."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from app.core.ratelimit import client_ip
from app.models import AuditLog

_FORBIDDEN_KEYS = {"password", "token", "secret", "api_key", "authorization"}


def _scrub(meta: dict | None) -> dict | None:
    if not meta:
        return meta
    return {k: ("[redacted]" if any(f in k.lower() for f in _FORBIDDEN_KEYS) else v) for k, v in meta.items()}


def record(db: Session, *, action: str, company_id: str | None, actor=None, entity_type: str | None = None,
           entity_id: str | None = None, meta: dict | None = None, request: Request | None = None) -> AuditLog:
    entry = AuditLog(
        company_id=company_id,
        actor_id=getattr(actor, "id", None),
        actor_email=getattr(actor, "email", None),
        action=action, entity_type=entity_type, entity_id=entity_id, meta=_scrub(meta),
        ip_address=(client_ip(request) if request else None),
        request_id=(getattr(request.state, "request_id", None) if request else None),
    )
    db.add(entry)
    return entry
