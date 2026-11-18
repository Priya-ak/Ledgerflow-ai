"""Report datasets + Excel (openpyxl) rendering. All queries are company-scoped."""
from __future__ import annotations

import io
from datetime import date, datetime

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import ApprovalRequest, Invoice, Supplier, User
from app.models.enums import InvoiceStatus
from app.services.analytics import invoice_trends
from app.services.invoices import latest_po_match, latest_validation
from app.services.money import ZERO

MONEY_FMT = '#,##0.00'
HEADER_FILL = PatternFill("solid", fgColor="1E293B")


def _invoice_query(company_id: str, filters: dict):
    stmt = select(Invoice).where(Invoice.company_id == company_id).options(selectinload(Invoice.supplier))
    if filters.get("status"):
        stmt = stmt.where(Invoice.status.in_(filters["status"].split(",")))
    else:
        stmt = stmt.where(Invoice.status != InvoiceStatus.ARCHIVED)
    if filters.get("supplier_id"):
        stmt = stmt.where(Invoice.supplier_id == filters["supplier_id"])
    if filters.get("date_from"):
        stmt = stmt.where(Invoice.invoice_date >= filters["date_from"])
    if filters.get("date_to"):
        stmt = stmt.where(Invoice.invoice_date <= filters["date_to"])
    return stmt.order_by(Invoice.invoice_date.desc().nulls_last(), Invoice.created_at.desc()).limit(5000)


def invoice_register(db: Session, company_id: str, filters: dict) -> dict:
    cols = ["Invoice No", "Invoice Date", "Due Date", "Supplier", "Supplier GSTIN", "PO No", "Taxable", "CGST", "SGST",
            "IGST", "Grand Total", "Status", "Validation", "Duplicate", "PO Match", "Payment"]
    rows = []
    for i in db.scalars(_invoice_query(company_id, filters)):
        rows.append([i.invoice_number, i.invoice_date, i.due_date, i.supplier.name if i.supplier else i.supplier_name_raw,
                     i.supplier_gstin_raw, i.po_number_ref, i.taxable_amount, i.cgst, i.sgst, i.igst, i.grand_total,
                     i.status, i.validation_status, i.duplicate_status, i.po_match_status, i.payment_status])
    return {"title": "Invoice Register", "columns": cols, "rows": rows, "money_cols": {6, 7, 8, 9, 10}, "total_cols": {6, 7, 8, 9, 10}}


def invoice_details(db: Session, company_id: str, filters: dict) -> dict:
    cols = ["Invoice No", "Invoice Date", "Supplier", "Line", "Description", "HSN/SAC", "Qty", "Unit", "Unit Price",
            "Discount", "Taxable", "GST %", "Tax", "Line Total"]
    rows = []
    for i in db.scalars(_invoice_query(company_id, filters).options(selectinload(Invoice.items))):
        for it in i.items:
            rows.append([i.invoice_number, i.invoice_date, i.supplier.name if i.supplier else i.supplier_name_raw, it.line_no,
                         it.description, it.hsn_sac, it.quantity, it.unit, it.unit_price, it.discount, it.taxable_value,
                         it.tax_rate, it.tax_amount, it.line_total])
    return {"title": "Invoice Details", "columns": cols, "rows": rows, "money_cols": {8, 9, 10, 12, 13}, "total_cols": {10, 12, 13}}


def supplier_report(db: Session, company_id: str, filters: dict) -> dict:
    cols = ["Code", "Supplier", "GSTIN", "Status", "Payment Terms (days)", "Invoices", "Total Invoiced", "Approved", "Exceptions"]
    agg: dict[str, list] = {}
    for i in db.scalars(_invoice_query(company_id, filters)):
        if i.supplier_id:
            a = agg.setdefault(i.supplier_id, [0, ZERO, ZERO, 0])
            a[0] += 1
            a[1] += i.grand_total or ZERO
            a[2] += (i.grand_total or ZERO) if i.status == InvoiceStatus.APPROVED else ZERO
            a[3] += i.validation_status == "failed"
    rows = []
    for s in db.scalars(select(Supplier).where(Supplier.company_id == company_id).order_by(Supplier.name)):
        a = agg.get(s.id, [0, ZERO, ZERO, 0])
        rows.append([s.code, s.name, s.gstin, s.status, s.payment_terms_days, a[0], a[1], a[2], a[3]])
    return {"title": "Supplier Report", "columns": cols, "rows": rows, "money_cols": {6, 7}, "total_cols": {5, 6, 7, 8}}


def validation_report(db: Session, company_id: str, filters: dict) -> dict:
    cols = ["Invoice No", "Supplier", "Grand Total", "Check", "Severity", "Expected", "Actual", "Difference", "Explanation", "Recommended Action"]
    rows = []
    for i in db.scalars(_invoice_query(company_id, filters)):
        v = latest_validation(db, i.id)
        if not v:
            continue
        for ch in v.report.get("checks", []):
            if not ch.get("passed") and ch.get("severity") != "info":
                rows.append([i.invoice_number, i.supplier.name if i.supplier else i.supplier_name_raw, i.grand_total,
                             ch.get("name"), ch.get("severity"), ch.get("expected"), ch.get("actual"), ch.get("difference"),
                             ch.get("explanation"), ch.get("recommended_action")])
    return {"title": "Validation Exceptions", "columns": cols, "rows": rows, "money_cols": {2}, "total_cols": set()}


def po_matching_report(db: Session, company_id: str, filters: dict) -> dict:
    cols = ["Invoice No", "Supplier", "PO No", "Match Status", "Issue"]
    rows = []
    for i in db.scalars(_invoice_query(company_id, filters)):
        p = latest_po_match(db, i.id)
        if not p:
            continue
        issues = p.report.get("issues") or ["No differences."]
        for issue in issues:
            rows.append([i.invoice_number, i.supplier.name if i.supplier else i.supplier_name_raw,
                         (p.report.get("purchase_order") or {}).get("po_number") or i.po_number_ref, p.status, issue])
    return {"title": "PO Matching", "columns": cols, "rows": rows, "money_cols": set(), "total_cols": set()}


def approval_report(db: Session, company_id: str, filters: dict) -> dict:
    cols = ["Invoice No", "Grand Total", "Submitted By", "Submitted At", "Level", "Approver", "Decision", "Comment", "Decided At", "Request Status"]
    users = {u.id: u.full_name for u in db.scalars(select(User).where(User.company_id == company_id))}
    rows = []
    stmt = (select(ApprovalRequest, Invoice).join(Invoice, Invoice.id == ApprovalRequest.invoice_id)
            .where(ApprovalRequest.company_id == company_id).options(selectinload(ApprovalRequest.steps))
            .order_by(ApprovalRequest.created_at.desc()).limit(5000))
    for req, inv in db.execute(stmt).all():
        base = [inv.invoice_number, inv.grand_total, users.get(req.submitted_by_id), req.created_at]
        if not req.steps:
            rows.append(base + [req.current_level, None, "pending", None, None, req.status])
        for s in req.steps:
            rows.append(base + [s.level, users.get(s.approver_id), s.decision, s.comment, s.created_at, req.status])
    return {"title": "Approval History", "columns": cols, "rows": rows, "money_cols": {1}, "total_cols": set()}


def monthly_summary(db: Session, company_id: str, filters: dict) -> dict:
    data = invoice_trends(db, company_id, months=12)
    from decimal import Decimal
    rows = [[m["month"], m["count"], Decimal(m["value"]), Decimal(m["approved_value"])] for m in data["monthly"]]
    return {"title": "Monthly Summary", "columns": ["Month", "Invoices", "Total Value", "Approved Value"],
            "rows": rows, "money_cols": {2, 3}, "total_cols": {1, 2, 3}}


REPORTS = {
    "invoices": invoice_register, "invoice-details": invoice_details, "suppliers": supplier_report,
    "validation": validation_report, "po-matching": po_matching_report, "approvals": approval_report,
    "monthly": monthly_summary,
}


def _cell(v):
    if isinstance(v, datetime):
        return v.replace(tzinfo=None)
    return v


def to_xlsx(datasets: list[dict], company_name: str) -> bytes:
    wb = Workbook()
    wb.remove(wb.active)
    for ds in datasets:
        ws = wb.create_sheet(ds["title"][:31])
        ws.append([f"{company_name} - {ds['title']}"])
        ws["A1"].font = Font(bold=True, size=13)
        ws.append([f"Generated {datetime.now().strftime('%d %b %Y %H:%M')} by LedgerFlow AI"])
        ws["A2"].font = Font(italic=True, color="64748B")
        ws.append([])
        ws.append(ds["columns"])
        for c in ws[4]:
            c.font, c.fill = Font(bold=True, color="FFFFFF"), HEADER_FILL
            c.alignment = Alignment(vertical="center")
        for r in ds["rows"]:
            ws.append([_cell(v) for v in r])
        first, last = 5, 4 + len(ds["rows"])
        widths = [len(str(c)) for c in ds["columns"]]
        for row in ws.iter_rows(min_row=first, max_row=last):
            for idx, c in enumerate(row):
                if idx in ds["money_cols"]:
                    c.number_format = MONEY_FMT
                elif isinstance(c.value, (date, datetime)):
                    c.number_format = "dd-mmm-yyyy"
                widths[idx] = max(widths[idx], min(len(str(c.value or "")), 60))
        if ds["rows"] and ds["total_cols"]:
            total_row = ["Total"] + [None] * (len(ds["columns"]) - 1)
            ws.append(total_row)
            tr = last + 1
            for idx in ds["total_cols"]:
                col = get_column_letter(idx + 1)
                c = ws.cell(row=tr, column=idx + 1, value=f"=SUM({col}{first}:{col}{last})")
                if idx in ds["money_cols"]:
                    c.number_format = MONEY_FMT
            for c in ws[tr]:
                c.font = Font(bold=True)
        for idx, w in enumerate(widths, 1):
            ws.column_dimensions[get_column_letter(idx)].width = max(10, w + 2)
        ws.freeze_panes = "A5"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
