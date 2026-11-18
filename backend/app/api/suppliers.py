from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.pagination import paginate
from app.core.database import get_db
from app.core.deps import CurrentUser, get_owned, require
from app.core.errors import BusinessRuleError, Conflict
from app.models import Invoice, PurchaseOrder, Supplier
from app.schemas.common import Page
from app.schemas.entities import SupplierIn, SupplierOut
from app.services import audit
from app.services.gst import validate_gstin

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _check_gstin(g: str | None) -> None:
    if g:
        ok, msg = validate_gstin(g)
        if not ok:
            raise BusinessRuleError(msg, details={"field": "gstin"})


@router.get("", response_model=Page[SupplierOut])
def list_suppliers(q: str | None = None, status: str | None = None, page: int = Query(1, ge=1),
                   page_size: int = Query(20, ge=1, le=100), sort: str = "name",
                   current: CurrentUser = Depends(require("suppliers:read")), db: Session = Depends(get_db)):
    stmt = select(Supplier).where(Supplier.company_id == current.company_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Supplier.name).like(like), func.lower(Supplier.code).like(like),
                              func.lower(Supplier.gstin).like(like)))
    stmt = stmt.where(Supplier.status == status) if status else stmt.where(Supplier.status != "archived")
    order = {"name": Supplier.name, "-name": Supplier.name.desc(), "created": Supplier.created_at.desc()}.get(sort, Supplier.name)
    return paginate(db, stmt.order_by(order), page, page_size, SupplierOut)


@router.post("", response_model=SupplierOut, status_code=201)
def create_supplier(body: SupplierIn, request: Request, current: CurrentUser = Depends(require("suppliers:write")),
                    db: Session = Depends(get_db)):
    _check_gstin(body.gstin)
    s = Supplier(company_id=current.company_id, **body.model_dump())
    db.add(s)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("A supplier with this code already exists.")
    audit.record(db, action="supplier.create", company_id=current.company_id, actor=current.user,
                 entity_type="supplier", entity_id=s.id, meta={"name": s.name, "code": s.code}, request=request)
    db.commit()
    return s


@router.get("/{supplier_id}", response_model=SupplierOut)
def get_supplier(supplier_id: str, current: CurrentUser = Depends(require("suppliers:read")), db: Session = Depends(get_db)):
    return get_owned(db, Supplier, supplier_id, current.company_id)


@router.put("/{supplier_id}", response_model=SupplierOut)
def update_supplier(supplier_id: str, body: SupplierIn, request: Request,
                    current: CurrentUser = Depends(require("suppliers:write")), db: Session = Depends(get_db)):
    s = get_owned(db, Supplier, supplier_id, current.company_id)
    _check_gstin(body.gstin)
    data = body.model_dump()
    changed = {k: [str(getattr(s, k)), str(v)] for k, v in data.items() if getattr(s, k) != v}
    for k, v in data.items():
        setattr(s, k, v)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise Conflict("A supplier with this code already exists.")
    audit.record(db, action="supplier.update", company_id=current.company_id, actor=current.user,
                 entity_type="supplier", entity_id=s.id, meta={"changes": changed}, request=request)
    db.commit()
    return s


@router.delete("/{supplier_id}", response_model=SupplierOut)
def delete_supplier(supplier_id: str, request: Request, hard: bool = False,
                    current: CurrentUser = Depends(require("suppliers:delete")), db: Session = Depends(get_db)):
    """Archives by default. hard=true deletes only if the supplier has no invoices or POs."""
    s = get_owned(db, Supplier, supplier_id, current.company_id)
    if hard:
        used = db.scalar(select(Invoice.id).where(Invoice.supplier_id == s.id).limit(1)) or \
            db.scalar(select(PurchaseOrder.id).where(PurchaseOrder.supplier_id == s.id).limit(1))
        if used:
            raise BusinessRuleError("Supplier has invoices or purchase orders; archive it instead.")
        audit.record(db, action="supplier.delete", company_id=current.company_id, actor=current.user,
                     entity_type="supplier", entity_id=s.id, meta={"name": s.name}, request=request)
        out = SupplierOut.model_validate(s)
        db.delete(s)
        db.commit()
        return out
    s.status = "archived"
    audit.record(db, action="supplier.archive", company_id=current.company_id, actor=current.user,
                 entity_type="supplier", entity_id=s.id, meta={"name": s.name}, request=request)
    db.commit()
    return s
