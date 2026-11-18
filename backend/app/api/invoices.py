from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.pagination import paginate
from app.core.database import get_db, money_sort
from app.core.deps import CurrentUser, get_owned, require
from app.core.errors import BusinessRuleError, Forbidden
from app.models import (
    ApprovalRequest, Document, DuplicateMatch, Invoice, InvoiceItem, PurchaseOrder, Supplier,
)
from app.models.enums import EDITABLE_STATUSES, InvoiceStatus
from app.schemas.common import Page
from app.schemas.entities import (
    ApproveIn, ExtractIn, InvoiceDetail, InvoiceIn, InvoiceListItem, MatchPOIn, RejectIn, ResolveDuplicateIn, SubmitIn,
)
from app.services import approvals as approval_svc
from app.services import audit
from app.services.duplicates import normalize_invoice_number
from app.services.invoices import company_settings, latest_po_match, latest_validation, run_checks, run_po_match
from app.services.email import deliver
from app.services.notifications import approvers_to_notify, submitter_decision
from app.services.processing import process_document

router = APIRouter(prefix="/invoices", tags=["invoices"])

SORTS = {
    "-created": Invoice.created_at.desc(), "created": Invoice.created_at,
    "-date": Invoice.invoice_date.desc(), "date": Invoice.invoice_date,
    "-amount": money_sort(Invoice.grand_total).desc(), "amount": money_sort(Invoice.grand_total),
    "number": Invoice.invoice_number,
}


def detail(db: Session, inv: Invoice) -> InvoiceDetail:
    db.refresh(inv)
    out = InvoiceDetail.model_validate(inv)
    v = latest_validation(db, inv.id)
    p = latest_po_match(db, inv.id)
    out.validation = v.report if v else None
    out.po_match = p.report if p else None
    out.duplicates = list(db.scalars(select(DuplicateMatch).where(DuplicateMatch.invoice_id == inv.id)
                                     .order_by(DuplicateMatch.score.desc())))
    out.approvals = list(db.scalars(select(ApprovalRequest).where(ApprovalRequest.invoice_id == inv.id)
                                    .options(selectinload(ApprovalRequest.steps)).order_by(ApprovalRequest.created_at.desc())))
    return out


@router.get("", response_model=Page[InvoiceListItem])
def list_invoices(
    q: str | None = None, status: str | None = None, supplier_id: str | None = None,
    validation_status: str | None = None, duplicate_status: str | None = None, po_match_status: str | None = None,
    date_from: date | None = None, date_to: date | None = None, include_archived: bool = False,
    sort: str = "-created", page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    current: CurrentUser = Depends(require("invoices:read")), db: Session = Depends(get_db),
):
    stmt = select(Invoice).outerjoin(Supplier).where(Invoice.company_id == current.company_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Invoice.invoice_number).like(like), func.lower(Supplier.name).like(like),
                              func.lower(Invoice.supplier_name_raw).like(like), func.lower(Invoice.po_number_ref).like(like)))
    if status:
        stmt = stmt.where(Invoice.status.in_(status.split(",")))
    elif not include_archived:
        stmt = stmt.where(Invoice.status != InvoiceStatus.ARCHIVED)
    for col, val in ((Invoice.supplier_id, supplier_id), (Invoice.validation_status, validation_status),
                     (Invoice.duplicate_status, duplicate_status), (Invoice.po_match_status, po_match_status)):
        if val:
            stmt = stmt.where(col == val)
    if date_from:
        stmt = stmt.where(Invoice.invoice_date >= date_from)
    if date_to:
        stmt = stmt.where(Invoice.invoice_date <= date_to)
    stmt = stmt.options(selectinload(Invoice.supplier)).order_by(SORTS.get(sort, Invoice.created_at.desc()), Invoice.id)
    return paginate(db, stmt, page, page_size, InvoiceListItem)


def _apply_body(db: Session, inv: Invoice, body: InvoiceIn, company_id: str) -> dict:
    data = body.model_dump(exclude_unset=True)
    items = data.pop("items", None)
    if data.get("supplier_id"):
        get_owned(db, Supplier, data["supplier_id"], company_id)
    if data.get("purchase_order_id"):
        get_owned(db, PurchaseOrder, data["purchase_order_id"], company_id)
    changes = {}
    for k, v in data.items():
        old = getattr(inv, k)
        if old != v:
            changes[k] = {"from": None if old is None else str(old), "to": None if v is None else str(v)}
            setattr(inv, k, v)
    if "invoice_number" in data:
        inv.invoice_number_normalized = normalize_invoice_number(inv.invoice_number)
    if items is not None:
        inv.items = [InvoiceItem(line_no=i, **it) for i, it in enumerate(items, 1)]
        changes["items"] = {"count": len(items)}
    if changes and inv.needs_review_fields:
        # Fields a human has now corrected no longer need review.
        inv.needs_review_fields = [f for f in inv.needs_review_fields
                                   if f.split(".")[-1] not in data and not (f == "items" and items)
                                   and not (f == "supplier.name" and "supplier_id" in data)]
    return changes


@router.post("", response_model=InvoiceDetail, status_code=201)
def create_invoice(body: InvoiceIn, request: Request, current: CurrentUser = Depends(require("invoices:write")),
                   db: Session = Depends(get_db)):
    """Manual invoice entry (no document)."""
    inv = Invoice(company_id=current.company_id, status=InvoiceStatus.DRAFT, created_by_id=current.id,
                  extraction_method="manual", needs_review_fields=[])
    db.add(inv)
    _apply_body(db, inv, body, current.company_id)
    db.flush()
    run_checks(db, inv)
    audit.record(db, action="invoice.create", company_id=current.company_id, actor=current.user, entity_type="invoice",
                 entity_id=inv.id, meta={"invoice_number": inv.invoice_number, "method": "manual"}, request=request)
    db.commit()
    return detail(db, inv)


@router.post("/extract", response_model=InvoiceDetail, status_code=201)
def extract(body: ExtractIn, request: Request, current: CurrentUser = Depends(require("invoices:write")),
            db: Session = Depends(get_db)):
    """Run OCR + extraction + checks on an uploaded document and create an invoice for review."""
    doc = get_owned(db, Document, body.document_id, current.company_id)
    inv, rec = process_document(db, doc, current.id)
    audit.record(db, action="invoice.extract", company_id=current.company_id, actor=current.user, entity_type="invoice",
                 entity_id=inv.id, request=request,
                 meta={"document_id": doc.id, "status": rec.status, "text_method": rec.text_method,
                       "extraction_method": rec.extraction_method, "duration_ms": rec.duration_ms,
                       "validation_status": inv.validation_status, "error": rec.error_message})
    db.commit()
    return detail(db, inv)


@router.get("/{invoice_id}", response_model=InvoiceDetail)
def get_invoice(invoice_id: str, current: CurrentUser = Depends(require("invoices:read")), db: Session = Depends(get_db)):
    return detail(db, get_owned(db, Invoice, invoice_id, current.company_id))


@router.put("/{invoice_id}", response_model=InvoiceDetail)
def update_invoice(invoice_id: str, body: InvoiceIn, request: Request,
                   current: CurrentUser = Depends(require("invoices:write")), db: Session = Depends(get_db)):
    """Human review/correction. Checks re-run automatically so results never go stale."""
    inv = get_owned(db, Invoice, invoice_id, current.company_id)
    if inv.status not in EDITABLE_STATUSES:
        raise BusinessRuleError(f"Invoices in status '{inv.status}' cannot be edited.")
    if inv.status == InvoiceStatus.REJECTED:
        inv.status = InvoiceStatus.REVIEW_REQUIRED
    changes = _apply_body(db, inv, body, current.company_id)
    db.flush()
    report = run_checks(db, inv)
    audit.record(db, action="invoice.correct", company_id=current.company_id, actor=current.user, entity_type="invoice",
                 entity_id=inv.id, meta={"changes": changes, "validation_status": report["status"]}, request=request)
    db.commit()
    return detail(db, inv)


@router.delete("/{invoice_id}", response_model=InvoiceDetail)
def archive_invoice(invoice_id: str, request: Request, current: CurrentUser = Depends(require("invoices:delete")),
                    db: Session = Depends(get_db)):
    """Invoices are archived, never hard-deleted, to preserve the audit trail."""
    inv = get_owned(db, Invoice, invoice_id, current.company_id)
    if inv.status == InvoiceStatus.PENDING_APPROVAL:
        raise BusinessRuleError("Withdraw or decide the approval before archiving.")
    prev = inv.status
    inv.status = InvoiceStatus.ARCHIVED
    inv.archived_at = datetime.now(timezone.utc)
    audit.record(db, action="invoice.archive", company_id=current.company_id, actor=current.user, entity_type="invoice",
                 entity_id=inv.id, meta={"previous_status": prev}, request=request)
    db.commit()
    return detail(db, inv)


@router.post("/{invoice_id}/validate", response_model=InvoiceDetail)
def validate(invoice_id: str, request: Request, current: CurrentUser = Depends(require("invoices:write")),
             db: Session = Depends(get_db)):
    inv = get_owned(db, Invoice, invoice_id, current.company_id)
    if inv.status in (InvoiceStatus.APPROVED, InvoiceStatus.ARCHIVED):
        raise BusinessRuleError(f"Invoice is {inv.status}; validation is locked.")
    report = run_checks(db, inv)
    audit.record(db, action="invoice.validate", company_id=current.company_id, actor=current.user, entity_type="invoice",
                 entity_id=inv.id, meta={"status": report["status"], "summary": report["summary"]}, request=request)
    db.commit()
    return detail(db, inv)


@router.post("/{invoice_id}/match-purchase-order", response_model=InvoiceDetail)
def match_po(invoice_id: str, body: MatchPOIn, request: Request,
             current: CurrentUser = Depends(require("invoices:write")), db: Session = Depends(get_db)):
    inv = get_owned(db, Invoice, invoice_id, current.company_id)
    if inv.status not in EDITABLE_STATUSES:
        raise BusinessRuleError(f"Invoice in status '{inv.status}' cannot be re-matched.")
    if body.purchase_order_id:
        po = get_owned(db, PurchaseOrder, body.purchase_order_id, current.company_id)
        inv.purchase_order_id, inv.po_number_ref = po.id, po.po_number
        db.flush()
    report = run_checks(db, inv)
    audit.record(db, action="invoice.po_match", company_id=current.company_id, actor=current.user, entity_type="invoice",
                 entity_id=inv.id, meta={"po_match_status": inv.po_match_status, "validation_status": report["status"]},
                 request=request)
    db.commit()
    return detail(db, inv)


@router.post("/{invoice_id}/duplicates/{match_id}/resolve", response_model=InvoiceDetail)
def resolve_duplicate(invoice_id: str, match_id: str, body: ResolveDuplicateIn, request: Request,
                      current: CurrentUser = Depends(require("duplicates:resolve")), db: Session = Depends(get_db)):
    inv = get_owned(db, Invoice, invoice_id, current.company_id)
    m = db.scalar(select(DuplicateMatch).where(DuplicateMatch.id == match_id, DuplicateMatch.invoice_id == inv.id))
    if m is None:
        raise BusinessRuleError("Duplicate match not found for this invoice.")
    m.resolution, m.resolution_note = body.resolution, body.note
    m.resolved_by_id, m.resolved_at = current.id, datetime.now(timezone.utc)
    db.flush()
    run_checks(db, inv)
    audit.record(db, action="invoice.duplicate_resolved", company_id=current.company_id, actor=current.user,
                 entity_type="invoice", entity_id=inv.id, request=request,
                 meta={"match_id": m.id, "matched_invoice_id": m.matched_invoice_id, "resolution": body.resolution,
                       "note": body.note})
    db.commit()
    return detail(db, inv)


@router.post("/{invoice_id}/submit", response_model=InvoiceDetail)
def submit(invoice_id: str, body: SubmitIn, request: Request, background: BackgroundTasks,
           current: CurrentUser = Depends(require("invoices:submit")), db: Session = Depends(get_db)):
    inv = get_owned(db, Invoice, invoice_id, current.company_id)
    run_checks(db, inv)  # never submit on stale results
    req = approval_svc.submit(db, inv, current.user, body.note)
    db.flush()
    audit.record(db, action="invoice.submit", company_id=current.company_id, actor=current.user, entity_type="invoice",
                 entity_id=inv.id, request=request,
                 meta={"approval_request_id": req.id, "levels": len(req.required_levels),
                       "validation_status": inv.validation_status, "grand_total": str(inv.grand_total)})
    db.commit()
    for email in approvers_to_notify(db, inv, req):
        background.add_task(deliver, email)
    return detail(db, inv)


@router.post("/{invoice_id}/approve", response_model=InvoiceDetail)
def approve(invoice_id: str, body: ApproveIn, request: Request, background: BackgroundTasks,
            current: CurrentUser = Depends(require("approvals:decide")), db: Session = Depends(get_db)):
    inv = get_owned(db, Invoice, invoice_id, current.company_id)
    if body.override_critical and not current.can("approvals:override"):
        raise Forbidden("Only admins can override critical validation errors.")
    req = approval_svc.approve(db, inv, current.user, body.comment, body.override_critical)
    audit.record(db, action="invoice.approve", company_id=current.company_id, actor=current.user, entity_type="invoice",
                 entity_id=inv.id, request=request,
                 meta={"approval_request_id": req.id, "level": req.current_level, "final": inv.status == InvoiceStatus.APPROVED,
                       "override_critical": body.override_critical, "comment": body.comment})
    db.commit()
    emails = approvers_to_notify(db, inv, req) if req.status == "pending" else submitter_decision(db, inv, req, current.user, None)
    for email in emails:
        background.add_task(deliver, email)
    return detail(db, inv)


@router.post("/{invoice_id}/reject", response_model=InvoiceDetail)
def reject(invoice_id: str, body: RejectIn, request: Request, background: BackgroundTasks,
           current: CurrentUser = Depends(require("approvals:decide")), db: Session = Depends(get_db)):
    inv = get_owned(db, Invoice, invoice_id, current.company_id)
    req = approval_svc.reject(db, inv, current.user, body.reason)
    audit.record(db, action="invoice.reject", company_id=current.company_id, actor=current.user, entity_type="invoice",
                 entity_id=inv.id, meta={"approval_request_id": req.id, "reason": body.reason}, request=request)
    db.commit()
    for email in submitter_decision(db, inv, req, current.user, body.reason):
        background.add_task(deliver, email)
    return detail(db, inv)
