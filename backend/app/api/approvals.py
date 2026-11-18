from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.deps import CurrentUser, require
from app.core.errors import NotFound
from app.models import ApprovalRequest, Invoice, Supplier
from app.schemas.common import Page
from app.schemas.entities import ApprovalRequestOut, InvoiceListItem, SupplierRef

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalListItem(ApprovalRequestOut):
    invoice: InvoiceListItem
    can_decide: bool = False


def _can_decide(req: ApprovalRequest, current: CurrentUser) -> bool:
    if req.status != "pending" or not current.can("approvals:decide"):
        return False
    level = next((l for l in req.required_levels if l["level"] == req.current_level), None)
    role_ok = level is not None and (current.role == "admin" or current.role == level["role"])
    already = any(s.approver_id == current.id and s.decision == "approved" for s in req.steps)
    return role_ok and not already


@router.get("", response_model=Page[ApprovalListItem])
def list_approvals(status: str | None = "pending", actionable: bool = False, page: int = Query(1, ge=1),
                   page_size: int = Query(20, ge=1, le=100), current: CurrentUser = Depends(require("approvals:read")),
                   db: Session = Depends(get_db)):
    stmt = (select(ApprovalRequest, Invoice).join(Invoice, Invoice.id == ApprovalRequest.invoice_id)
            .where(ApprovalRequest.company_id == current.company_id)
            .options(selectinload(ApprovalRequest.steps)).order_by(ApprovalRequest.created_at.desc()))
    if status and status != "all":
        stmt = stmt.where(ApprovalRequest.status == status)
    rows = db.execute(stmt.limit(1000)).all()
    items = []
    for req, inv in rows:
        sup = db.get(Supplier, inv.supplier_id) if inv.supplier_id else None
        item = ApprovalListItem.model_validate({**ApprovalRequestOut.model_validate(req).model_dump(),
                                                "invoice": InvoiceListItem.model_validate(inv).model_copy(update={"supplier": SupplierRef.model_validate(sup) if sup else None}),
                                                "can_decide": _can_decide(req, current) and (req.submitted_by_id != current.id)})
        if actionable and not item.can_decide:
            continue
        items.append(item)
    total = len(items)
    start = (page - 1) * page_size
    return Page(items=items[start:start + page_size], total=total, page=page, page_size=page_size)


@router.get("/{approval_id}", response_model=ApprovalRequestOut)
def get_approval(approval_id: str, current: CurrentUser = Depends(require("approvals:read")), db: Session = Depends(get_db)):
    req = db.scalar(select(ApprovalRequest).where(ApprovalRequest.id == approval_id,
                                                  ApprovalRequest.company_id == current.company_id))
    if req is None:
        raise NotFound("Approval request not found.")
    return req
