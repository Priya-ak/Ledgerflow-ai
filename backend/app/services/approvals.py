"""Human approval workflow with configurable multi-level policy (default: single level).

No AI participates in approvals. Critical validation errors block approval unless
the company policy explicitly enables an admin override with a written reason.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError, Forbidden
from app.models import ApprovalPolicy, ApprovalRequest, ApprovalStep, Invoice, User
from app.models.enums import ApprovalStatus, DuplicateStatus, InvoiceStatus, Role

DEFAULT_LEVELS = [{"level": 1, "name": "Manager approval", "role": "approver", "min_amount": "0"}]
SUBMITTABLE = {InvoiceStatus.EXTRACTED, InvoiceStatus.REVIEW_REQUIRED, InvoiceStatus.REJECTED, InvoiceStatus.DRAFT}


def get_policy(db: Session, company_id: str) -> ApprovalPolicy:
    p = db.scalar(select(ApprovalPolicy).where(ApprovalPolicy.company_id == company_id))
    if p is None:
        p = ApprovalPolicy(company_id=company_id, levels=DEFAULT_LEVELS)
        db.add(p)
        db.flush()
    return p


def applicable_levels(policy: ApprovalPolicy, amount: Decimal | None) -> list[dict]:
    amt = amount or Decimal("0")
    levels = [lv for lv in sorted(policy.levels, key=lambda l: l["level"]) if amt >= Decimal(str(lv.get("min_amount", "0")))]
    return levels or sorted(policy.levels, key=lambda l: l["level"])[:1]


def active_request(db: Session, invoice_id: str) -> ApprovalRequest | None:
    return db.scalar(select(ApprovalRequest).where(ApprovalRequest.invoice_id == invoice_id,
                                                   ApprovalRequest.status == ApprovalStatus.PENDING))


def submit(db: Session, inv: Invoice, user: User, note: str | None) -> ApprovalRequest:
    if inv.status not in SUBMITTABLE:
        raise BusinessRuleError(f"Invoice in status '{inv.status}' cannot be submitted.")
    if inv.validation_status == "not_run":
        raise BusinessRuleError("Run validation before submitting.")
    if inv.duplicate_status == DuplicateStatus.DUPLICATE:
        raise BusinessRuleError("Resolve the duplicate warning before submitting.")
    missing = [f for f, v in {"invoice number": inv.invoice_number, "invoice date": inv.invoice_date,
                              "supplier": inv.supplier_id, "grand total": inv.grand_total}.items() if not v]
    if missing:
        raise BusinessRuleError(f"Complete required fields before submitting: {', '.join(missing)}.")
    policy = get_policy(db, inv.company_id)
    req = ApprovalRequest(company_id=inv.company_id, invoice_id=inv.id, submitted_by_id=user.id,
                          required_levels=applicable_levels(policy, inv.grand_total), current_level=1,
                          submission_note=note)
    db.add(req)
    inv.status = InvoiceStatus.PENDING_APPROVAL
    inv.submitted_by_id, inv.submitted_at = user.id, datetime.now(timezone.utc)
    db.flush()
    return req


def _check_can_decide(db: Session, inv: Invoice, req: ApprovalRequest, user: User) -> dict:
    policy = get_policy(db, inv.company_id)
    if req.submitted_by_id == user.id and not policy.allow_self_approval:
        raise Forbidden("You cannot approve or reject an invoice you submitted.")
    level = next(lv for lv in req.required_levels if lv["level"] == req.current_level)
    if user.role != Role.ADMIN and user.role != level["role"]:
        raise Forbidden(f"Level {level['level']} requires the '{level['role']}' role.")
    if any(s.approver_id == user.id and s.decision == "approved" for s in req.steps):
        raise Forbidden("You have already approved an earlier level of this invoice.")
    return level


def approve(db: Session, inv: Invoice, user: User, comment: str | None, override_critical: bool = False) -> ApprovalRequest:
    req = active_request(db, inv.id)
    if req is None or inv.status != InvoiceStatus.PENDING_APPROVAL:
        raise BusinessRuleError("Invoice is not pending approval.")
    level = _check_can_decide(db, inv, req, user)
    if inv.has_critical_errors:
        policy = get_policy(db, inv.company_id)
        if not override_critical:
            raise BusinessRuleError("Invoice has unresolved critical validation errors and cannot be approved.")
        if not (policy.allow_critical_override and user.role == Role.ADMIN):
            raise Forbidden("Critical-error override is not permitted by company policy.")
        if not comment or len(comment.strip()) < 10:
            raise BusinessRuleError("An override requires a written justification (min. 10 characters).")
    db.add(ApprovalStep(request=req, level=level["level"], approver_id=user.id, decision="approved",
                        comment=comment, override_critical=override_critical and inv.has_critical_errors))
    levels = [lv["level"] for lv in req.required_levels]
    if req.current_level >= max(levels):
        req.status = ApprovalStatus.APPROVED
        req.completed_at = datetime.now(timezone.utc)
        inv.status = InvoiceStatus.APPROVED
        inv.decided_at = req.completed_at
    else:
        req.current_level = min(l for l in levels if l > req.current_level)
    return req


def reject(db: Session, inv: Invoice, user: User, reason: str) -> ApprovalRequest:
    if not reason or len(reason.strip()) < 5:
        raise BusinessRuleError("A rejection reason is required (min. 5 characters).")
    req = active_request(db, inv.id)
    if req is None or inv.status != InvoiceStatus.PENDING_APPROVAL:
        raise BusinessRuleError("Invoice is not pending approval.")
    level = _check_can_decide(db, inv, req, user)
    db.add(ApprovalStep(request=req, level=level["level"], approver_id=user.id, decision="rejected", comment=reason.strip()))
    req.status = ApprovalStatus.REJECTED
    req.completed_at = datetime.now(timezone.utc)
    inv.status = InvoiceStatus.REJECTED
    inv.decided_at = req.completed_at
    return req
