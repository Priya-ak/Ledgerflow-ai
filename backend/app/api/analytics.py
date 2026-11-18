from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(current: CurrentUser = Depends(require("analytics:read")), db: Session = Depends(get_db)):
    return analytics.overview(db, current.company_id)


@router.get("/invoices")
def invoices(months: int = Query(12, ge=1, le=36), current: CurrentUser = Depends(require("analytics:read")),
             db: Session = Depends(get_db)):
    return analytics.invoice_trends(db, current.company_id, months)


@router.get("/approvals")
def approvals(months: int = Query(6, ge=1, le=36), current: CurrentUser = Depends(require("analytics:read")),
              db: Session = Depends(get_db)):
    return analytics.approval_trends(db, current.company_id, current.id, months)


@router.get("/suppliers")
def suppliers(limit: int = Query(10, ge=1, le=50), current: CurrentUser = Depends(require("analytics:read")),
              db: Session = Depends(get_db)):
    return analytics.supplier_stats(db, current.company_id, limit)
