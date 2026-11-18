"""Database-backed analytics, always scoped to one company.

MVP note: monthly bucketing is done in Python over a column projection (portable
across SQLite/PostgreSQL). At larger volumes, move to SQL date_trunc views.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import money_sort

from app.models import ApprovalRequest, ApprovalStep, Invoice, PurchaseOrder, Supplier, ValidationResult
from app.models.enums import InvoiceStatus
from app.services.money import ZERO, fmt

ACTIVE = Invoice.status != InvoiceStatus.ARCHIVED


def _month(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _last_months(n: int, today: date) -> list[str]:
    out, y, m = [], today.year, today.month
    for _ in range(n):
        out.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return list(reversed(out))


def overview(db: Session, company_id: str) -> dict:
    rows = db.execute(select(Invoice.status, Invoice.grand_total, Invoice.validation_status, Invoice.duplicate_status,
                             Invoice.needs_review_fields)
                      .where(Invoice.company_id == company_id, ACTIVE)).all()
    by_status: Counter = Counter()
    amount_by_status: dict[str, Decimal] = defaultdict(lambda: ZERO)
    total = ZERO
    dup = exceptions = 0
    for st, amt, vst, dst, _ in rows:
        by_status[st] += 1
        amount_by_status[st] += amt or ZERO
        total += amt or ZERO
        dup += dst in ("duplicate", "possible_duplicate")
        exceptions += vst == "failed"
    suppliers = db.scalar(select(func.count()).select_from(Supplier).where(Supplier.company_id == company_id, Supplier.status == "active"))
    open_pos = db.scalar(select(func.count()).select_from(PurchaseOrder).where(
        PurchaseOrder.company_id == company_id, PurchaseOrder.status.in_(["open", "partially_invoiced"])))
    return {
        "total_invoices": len(rows), "total_value": fmt(total),
        "approved_count": by_status[InvoiceStatus.APPROVED], "approved_amount": fmt(amount_by_status[InvoiceStatus.APPROVED]),
        "pending_count": by_status[InvoiceStatus.PENDING_APPROVAL], "pending_amount": fmt(amount_by_status[InvoiceStatus.PENDING_APPROVAL]),
        "rejected_count": by_status[InvoiceStatus.REJECTED], "rejected_amount": fmt(amount_by_status[InvoiceStatus.REJECTED]),
        "review_required_count": by_status[InvoiceStatus.REVIEW_REQUIRED],
        "ready_to_submit_count": by_status[InvoiceStatus.EXTRACTED],
        "failed_processing_count": by_status[InvoiceStatus.FAILED_PROCESSING],
        "duplicate_count": dup, "validation_exception_count": exceptions,
        "active_suppliers": suppliers or 0, "open_purchase_orders": open_pos or 0,
        "status_distribution": [{"status": k, "count": v} for k, v in sorted(by_status.items())],
    }


def invoice_trends(db: Session, company_id: str, months: int = 12, today: date | None = None) -> dict:
    today = today or date.today()
    keys = _last_months(months, today)
    buckets = {k: {"month": k, "count": 0, "value": ZERO, "approved_value": ZERO} for k in keys}
    rows = db.execute(select(Invoice.invoice_date, Invoice.created_at, Invoice.grand_total, Invoice.status)
                      .where(Invoice.company_id == company_id, ACTIVE)).all()
    for d, created, amt, st in rows:
        k = _month(d or created.date())
        if k in buckets:
            b = buckets[k]
            b["count"] += 1
            b["value"] += amt or ZERO
            if st == InvoiceStatus.APPROVED:
                b["approved_value"] += amt or ZERO
    # Validation issue distribution from the latest report per invoice.
    latest = (select(ValidationResult.invoice_id, func.max(ValidationResult.created_at).label("mx"))
              .where(ValidationResult.company_id == company_id).group_by(ValidationResult.invoice_id).subquery())
    reports = db.scalars(select(ValidationResult.report).join(
        latest, (ValidationResult.invoice_id == latest.c.invoice_id) & (ValidationResult.created_at == latest.c.mx))
        .join(Invoice, Invoice.id == ValidationResult.invoice_id).where(ACTIVE)).all()
    issues: Counter = Counter()
    for rep in reports:
        for ch in rep.get("checks", []):
            if not ch.get("passed") and ch.get("severity") in ("critical", "warning"):
                issues[ch.get("name")] += 1
    return {
        "monthly": [{**b, "value": fmt(b["value"]), "approved_value": fmt(b["approved_value"])} for b in buckets.values()],
        "validation_issues": [{"issue": k, "count": v} for k, v in issues.most_common(10)],
    }


def approval_trends(db: Session, company_id: str, user_id: str | None = None, months: int = 6, today: date | None = None) -> dict:
    today = today or date.today()
    keys = _last_months(months, today)
    buckets = {k: {"month": k, "approved": 0, "rejected": 0} for k in keys}
    rows = db.execute(select(ApprovalRequest.status, ApprovalRequest.created_at, ApprovalRequest.completed_at)
                      .where(ApprovalRequest.company_id == company_id)).all()
    durations = []
    for st, created, done in rows:
        if done is None:
            continue
        k = _month(done.date())
        if k in buckets and st in ("approved", "rejected"):
            buckets[k][st] += 1
        durations.append((done - created).total_seconds() / 3600)
    pending = db.execute(select(Invoice.id, Invoice.invoice_number, Invoice.grand_total, Invoice.submitted_at,
                                Supplier.name).outerjoin(Supplier)
                         .where(Invoice.company_id == company_id, Invoice.status == InvoiceStatus.PENDING_APPROVAL)
                         .order_by(money_sort(Invoice.grand_total).desc()).limit(5)).all()
    mine = {}
    if user_id:
        decisions = db.execute(select(ApprovalStep.decision, func.count()).join(ApprovalRequest)
                               .where(ApprovalRequest.company_id == company_id, ApprovalStep.approver_id == user_id)
                               .group_by(ApprovalStep.decision)).all()
        mine = {d: c for d, c in decisions}
    return {
        "monthly": list(buckets.values()),
        "average_hours_to_decision": round(sum(durations) / len(durations), 1) if durations else None,
        "high_value_pending": [{"id": i, "invoice_number": n, "grand_total": fmt(a), "supplier": s,
                                "submitted_at": sub.isoformat() if sub else None} for i, n, a, sub, s in pending],
        "my_decisions": mine,
    }


def supplier_stats(db: Session, company_id: str, limit: int = 10) -> dict:
    rows = db.execute(select(Supplier.id, Supplier.name, func.count(Invoice.id), Invoice.grand_total, Invoice.validation_status)
                      .join(Invoice, Invoice.supplier_id == Supplier.id)
                      .where(Supplier.company_id == company_id, ACTIVE)
                      .group_by(Supplier.id, Supplier.name, Invoice.id, Invoice.grand_total, Invoice.validation_status)).all()
    agg: dict[str, dict] = {}
    for sid, name, _, amt, vst in rows:
        a = agg.setdefault(sid, {"supplier_id": sid, "name": name, "invoice_count": 0, "total": ZERO, "exceptions": 0})
        a["invoice_count"] += 1
        a["total"] += amt or ZERO
        a["exceptions"] += vst == "failed"
    top = sorted(agg.values(), key=lambda x: x["total"], reverse=True)[:limit]
    return {"suppliers": [{**s, "total": fmt(s["total"])} for s in top]}
