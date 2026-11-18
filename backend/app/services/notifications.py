"""Builds workflow emails. Sending happens in background tasks (see services/email.py)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApprovalRequest, Invoice, User
from app.models.enums import Role
from app.services.email import Email, approval_requested_email, invoice_decided_email
from app.services.invoices import company_settings
from app.services.money import fmt


def _amount(inv: Invoice) -> str:
    return f"₹{fmt(inv.grand_total)}" if inv.grand_total is not None else "amount not set"


def approvers_to_notify(db: Session, inv: Invoice, req: ApprovalRequest) -> list[Email]:
    if req.status != "pending" or not company_settings(db, inv.company_id).notify_approvers:
        return []
    level = next(l for l in req.required_levels if l["level"] == req.current_level)
    already = {s.approver_id for s in req.steps if s.decision == "approved"}
    roles = {level["role"], Role.ADMIN} if level["role"] == Role.ADMIN else {level["role"]}
    users = db.scalars(select(User).where(User.company_id == inv.company_id, User.is_active.is_(True),
                                          User.role.in_(roles))).all()
    submitter = db.get(User, req.submitted_by_id)
    return [approval_requested_email(
        u.email, u.full_name, invoice_id=inv.id, invoice_number=inv.invoice_number,
        supplier=inv.supplier.name if inv.supplier else inv.supplier_name_raw, amount=_amount(inv),
        level_name=level["name"], submitted_by=submitter.full_name if submitter else "A colleague",
        company_id=inv.company_id, user_id=u.id, validation_status=inv.validation_status)
        for u in users if u.id != req.submitted_by_id and u.id not in already]


def submitter_decision(db: Session, inv: Invoice, req: ApprovalRequest, actor: User, reason: str | None) -> list[Email]:
    if req.status not in ("approved", "rejected"):
        return []
    submitter = db.get(User, req.submitted_by_id)
    if not submitter or not submitter.is_active or submitter.id == actor.id:
        return []
    return [invoice_decided_email(submitter.email, submitter.full_name, invoice_id=inv.id,
                                  invoice_number=inv.invoice_number, amount=_amount(inv), decision=req.status,
                                  decided_by=actor.full_name, reason=reason, company_id=inv.company_id,
                                  user_id=submitter.id)]
