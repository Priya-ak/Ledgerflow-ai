from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.pagination import paginate
from app.core.database import get_db
from app.core.deps import CurrentUser, get_owned, require
from app.core.errors import BusinessRuleError, Conflict
from app.models import Invoice, PurchaseOrder, PurchaseOrderItem, Supplier
from app.schemas.common import Page
from app.schemas.entities import PODetail, POIn, POOut
from app.services import audit
from app.services.invoices import recompute_po_totals

router = APIRouter(prefix="/purchase-orders", tags=["purchase orders"])


def _apply(po: PurchaseOrder, body: POIn) -> None:
    po.supplier_id, po.po_number, po.po_date = body.supplier_id, body.po_number.strip(), body.po_date
    po.expected_delivery_date, po.status, po.notes = body.expected_delivery_date, body.status, body.notes
    po.items = [PurchaseOrderItem(line_no=i, line_total=0, **it.model_dump()) for i, it in enumerate(body.items, 1)]
    recompute_po_totals(po)


@router.get("", response_model=Page[POOut])
def list_pos(q: str | None = None, status: str | None = None, supplier_id: str | None = None,
             page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
             current: CurrentUser = Depends(require("po:read")), db: Session = Depends(get_db)):
    stmt = select(PurchaseOrder).join(Supplier).where(PurchaseOrder.company_id == current.company_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(PurchaseOrder.po_number).like(like), func.lower(Supplier.name).like(like)))
    if status:
        stmt = stmt.where(PurchaseOrder.status == status)
    if supplier_id:
        stmt = stmt.where(PurchaseOrder.supplier_id == supplier_id)
    stmt = stmt.options(selectinload(PurchaseOrder.supplier)).order_by(PurchaseOrder.po_date.desc())
    return paginate(db, stmt, page, page_size, POOut)


@router.post("", response_model=PODetail, status_code=201)
def create_po(body: POIn, request: Request, current: CurrentUser = Depends(require("po:write")), db: Session = Depends(get_db)):
    get_owned(db, Supplier, body.supplier_id, current.company_id)
    po = PurchaseOrder(company_id=current.company_id, created_by_id=current.id)
    _apply(po, body)
    db.add(po)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("A purchase order with this number already exists.")
    audit.record(db, action="po.create", company_id=current.company_id, actor=current.user, entity_type="purchase_order",
                 entity_id=po.id, meta={"po_number": po.po_number, "total": str(po.total_amount)}, request=request)
    db.commit()
    return po


@router.get("/{po_id}", response_model=PODetail)
def get_po(po_id: str, current: CurrentUser = Depends(require("po:read")), db: Session = Depends(get_db)):
    return get_owned(db, PurchaseOrder, po_id, current.company_id)


@router.put("/{po_id}", response_model=PODetail)
def update_po(po_id: str, body: POIn, request: Request, current: CurrentUser = Depends(require("po:write")),
              db: Session = Depends(get_db)):
    po = get_owned(db, PurchaseOrder, po_id, current.company_id)
    get_owned(db, Supplier, body.supplier_id, current.company_id)
    if po.status in ("closed", "cancelled"):
        raise BusinessRuleError(f"A {po.status} purchase order cannot be edited.")
    before = str(po.total_amount)
    _apply(po, body)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("A purchase order with this number already exists.")
    audit.record(db, action="po.update", company_id=current.company_id, actor=current.user, entity_type="purchase_order",
                 entity_id=po.id, meta={"total_before": before, "total_after": str(po.total_amount)}, request=request)
    db.commit()
    return po


@router.delete("/{po_id}", response_model=POOut)
def delete_po(po_id: str, request: Request, current: CurrentUser = Depends(require("po:delete")), db: Session = Depends(get_db)):
    """Cancels a PO referenced by invoices; deletes it otherwise."""
    po = get_owned(db, PurchaseOrder, po_id, current.company_id)
    out = POOut.model_validate(po)
    if db.scalar(select(Invoice.id).where(Invoice.purchase_order_id == po.id).limit(1)):
        po.status = "cancelled"
        action = "po.cancel"
        out = POOut.model_validate(po)
    else:
        db.delete(po)
        action = "po.delete"
    audit.record(db, action=action, company_id=current.company_id, actor=current.user, entity_type="purchase_order",
                 entity_id=po_id, meta={"po_number": out.po_number}, request=request)
    db.commit()
    return out
