from __future__ import annotations

from datetime import date, datetime, time, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.pagination import paginate
from app.core.database import get_db
from app.core.deps import CurrentUser, require
from app.models import AuditLog
from app.schemas.common import Page
from app.schemas.entities import AuditLogOut

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogOut])
def list_audit_logs(action: str | None = None, entity_type: str | None = None, entity_id: str | None = None,
                    actor_id: str | None = None, date_from: date | None = None, date_to: date | None = None,
                    page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=100),
                    current: CurrentUser = Depends(require("audit:read")), db: Session = Depends(get_db)):
    """Read-only. There are intentionally no endpoints to modify or delete audit entries."""
    stmt = select(AuditLog).where(AuditLog.company_id == current.company_id)
    if action:
        stmt = stmt.where(AuditLog.action.like(f"{action}%"))
    for col, val in ((AuditLog.entity_type, entity_type), (AuditLog.entity_id, entity_id), (AuditLog.actor_id, actor_id)):
        if val:
            stmt = stmt.where(col == val)
    if date_from:
        stmt = stmt.where(AuditLog.created_at >= datetime.combine(date_from, time.min, timezone.utc))
    if date_to:
        stmt = stmt.where(AuditLog.created_at <= datetime.combine(date_to, time.max, timezone.utc))
    return paginate(db, stmt.order_by(AuditLog.created_at.desc()), page, page_size, AuditLogOut)


@router.get("/entity/{entity_id}", response_model=list[AuditLogOut])
def entity_history(entity_id: str, current: CurrentUser = Depends(require("invoices:read")), db: Session = Depends(get_db)):
    """Activity timeline for one record (available to all roles that can read invoices)."""
    return list(db.scalars(select(AuditLog).where(AuditLog.company_id == current.company_id, AuditLog.entity_id == entity_id)
                           .order_by(AuditLog.created_at.desc()).limit(200)))
