"""Invoice orchestration: supplier/PO resolution and the check pipeline
(duplicates -> PO match -> validation). Statuses are derived deterministically.
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    CompanySettings, Invoice, InvoiceItem, PoMatchResult, PurchaseOrder, Supplier, ValidationResult,
)
from app.models.enums import EDITABLE_STATUSES, InvoiceStatus, PoMatchStatus
from app.schemas.extraction import ExtractedInvoice
from app.services.duplicates import detect_duplicates, normalize_invoice_number
from app.services.gst import normalize_gstin
from app.services.money import ZERO, q2
from app.services.po_matching import Tolerances, compare_totals, match_lines
from app.services.validation import InvoiceInput, LineInput, ValidationContext, validate_invoice


def company_settings(db: Session, company_id: str) -> CompanySettings:
    cs = db.scalar(select(CompanySettings).where(CompanySettings.company_id == company_id))
    if cs is None:
        cs = CompanySettings(company_id=company_id)
        db.add(cs)
        db.flush()
    return cs


def resolve_supplier(db: Session, company_id: str, gstin: str | None, name: str | None) -> Supplier | None:
    g = normalize_gstin(gstin)
    if g:
        s = db.scalar(select(Supplier).where(Supplier.company_id == company_id, Supplier.gstin == g, Supplier.status != "archived"))
        if s:
            return s
    if name:
        return db.scalar(select(Supplier).where(Supplier.company_id == company_id,
                                                func.lower(Supplier.name) == name.strip().lower(), Supplier.status != "archived"))
    return None


def resolve_po(db: Session, company_id: str, po_number: str | None) -> PurchaseOrder | None:
    if not po_number:
        return None
    return db.scalar(select(PurchaseOrder).where(PurchaseOrder.company_id == company_id,
                                                 func.upper(PurchaseOrder.po_number) == po_number.strip().upper()))


def apply_extraction(db: Session, inv: Invoice, ex: ExtractedInvoice) -> None:
    inv.extracted_data = ex.model_dump(mode="json")
    inv.extraction_method = ex.extraction_metadata.method
    inv.needs_review_fields = ex.extraction_metadata.review_fields
    inv.invoice_number = ex.invoice.invoice_number
    inv.invoice_number_normalized = normalize_invoice_number(ex.invoice.invoice_number)
    inv.invoice_date = ex.invoice.invoice_date
    inv.due_date = ex.invoice.due_date
    inv.po_number_ref = ex.invoice.purchase_order_number
    inv.currency = ex.invoice.currency or "INR"
    inv.supplier_name_raw = ex.supplier.name
    inv.supplier_gstin_raw = normalize_gstin(ex.supplier.gstin)
    inv.supplier_address_raw = ex.supplier.address
    inv.buyer_name, inv.buyer_gstin, inv.buyer_address = ex.buyer.name, normalize_gstin(ex.buyer.gstin), ex.buyer.address
    s = ex.summary
    inv.subtotal, inv.discount, inv.taxable_amount = s.subtotal, s.discount, s.taxable_total
    inv.cgst, inv.sgst, inv.igst, inv.other_charges = s.cgst, s.sgst, s.igst, s.other_charges
    inv.total_tax = s.total_tax if s.total_tax is not None else (
        q2(sum((v for v in (s.cgst, s.sgst, s.igst) if v is not None), ZERO)) if any(v is not None for v in (s.cgst, s.sgst, s.igst)) else None)
    inv.grand_total = s.grand_total
    inv.items = [InvoiceItem(line_no=i, **it.model_dump()) for i, it in enumerate(ex.items, 1)]
    supplier = resolve_supplier(db, inv.company_id, ex.supplier.gstin, ex.supplier.name)
    inv.supplier_id = supplier.id if supplier else None
    po = resolve_po(db, inv.company_id, ex.invoice.purchase_order_number)
    inv.purchase_order_id = po.id if po else None


def to_validation_input(inv: Invoice) -> InvoiceInput:
    supplier_name = inv.supplier.name if inv.supplier else inv.supplier_name_raw
    return InvoiceInput(
        invoice_number=inv.invoice_number, invoice_date=inv.invoice_date, due_date=inv.due_date,
        supplier_id=inv.supplier_id, supplier_name=supplier_name, supplier_gstin=inv.supplier_gstin_raw,
        buyer_gstin=inv.buyer_gstin, subtotal=inv.subtotal, discount=inv.discount, taxable_amount=inv.taxable_amount,
        cgst=inv.cgst, sgst=inv.sgst, igst=inv.igst, other_charges=inv.other_charges, total_tax=inv.total_tax,
        grand_total=inv.grand_total,
        items=[LineInput(line_no=i.line_no, description=i.description, quantity=i.quantity, unit_price=i.unit_price,
                         discount=i.discount, taxable_value=i.taxable_value, tax_rate=i.tax_rate,
                         tax_amount=i.tax_amount, line_total=i.line_total) for i in inv.items],
    )


def run_po_match(db: Session, inv: Invoice, cs: CompanySettings) -> dict:
    tol = Tolerances(price_pct=cs.po_price_tolerance_pct, qty_pct=cs.po_qty_tolerance_pct, amount=cs.amount_tolerance)
    po = inv.purchase_order
    if po is None and inv.po_number_ref:
        po = resolve_po(db, inv.company_id, inv.po_number_ref)
        inv.purchase_order_id = po.id if po else None
        inv.purchase_order = po
    if po is None:
        status = PoMatchStatus.REQUIRES_REVIEW if inv.po_number_ref else PoMatchStatus.NO_PO_FOUND
        report = {"status": str(status), "purchase_order": None,
                  "issues": [f"PO '{inv.po_number_ref}' referenced on the invoice was not found."] if inv.po_number_ref
                  else ["No purchase order is referenced on this invoice."],
                  "matched_items": [], "extra_items": [], "missing_items": []}
    else:
        supplier_ok = inv.supplier_id is not None and inv.supplier_id == po.supplier_id
        report = match_lines(inv.items, po.items, tol, supplier_ok)
        report["purchase_order"] = {"id": po.id, "po_number": po.po_number, "supplier_id": po.supplier_id}
        report["totals"] = compare_totals(inv.grand_total, po.total_amount, tol)
        if report["totals"].get("exceeds_po"):
            report["issues"].append(f"Invoice total exceeds PO total by {report['totals']['difference']}.")
            if report["status"] == PoMatchStatus.MATCHED:
                report["status"] = str(PoMatchStatus.PARTIALLY_MATCHED)
    inv.po_match_status = report["status"]
    db.add(PoMatchResult(company_id=inv.company_id, invoice_id=inv.id, purchase_order_id=po.id if po else None,
                         status=report["status"], report=report))
    return report


def run_checks(db: Session, inv: Invoice) -> dict:
    """Duplicates -> PO match -> validation. Returns the validation report."""
    cs = company_settings(db, inv.company_id)
    db.flush()
    db.refresh(inv)
    detect_duplicates(db, inv, cs.duplicate_window_days)
    run_po_match(db, inv, cs)
    supplier = inv.supplier
    ctx = ValidationContext(
        amount_tolerance=cs.amount_tolerance,
        supplier_master_gstin=supplier.gstin if supplier else None,
        supplier_master_status=supplier.status if supplier else None,
        duplicate_status=inv.duplicate_status, po_match_status=inv.po_match_status,
    )
    report = validate_invoice(to_validation_input(inv), ctx)
    inv.validation_status = report["status"]
    inv.has_critical_errors = report["has_critical_errors"]
    db.add(ValidationResult(company_id=inv.company_id, invoice_id=inv.id, status=report["status"], report=report))
    if inv.status in EDITABLE_STATUSES and inv.status != InvoiceStatus.REJECTED:
        clean = report["status"] == "passed" and not inv.needs_review_fields
        inv.status = InvoiceStatus.EXTRACTED if clean else InvoiceStatus.REVIEW_REQUIRED
    return report


def latest_validation(db: Session, invoice_id: str) -> ValidationResult | None:
    return db.scalar(select(ValidationResult).where(ValidationResult.invoice_id == invoice_id)
                     .order_by(ValidationResult.created_at.desc()).limit(1))


def latest_po_match(db: Session, invoice_id: str) -> PoMatchResult | None:
    return db.scalar(select(PoMatchResult).where(PoMatchResult.invoice_id == invoice_id)
                     .order_by(PoMatchResult.created_at.desc()).limit(1))


def recompute_po_totals(po: PurchaseOrder) -> None:
    sub = tax = Decimal("0")
    for it in po.items:
        it.line_total = q2(it.quantity * it.unit_price * (1 + it.tax_rate / 100))
        sub += q2(it.quantity * it.unit_price)
        tax += q2(it.quantity * it.unit_price * it.tax_rate / 100)
    po.subtotal, po.tax_total, po.total_amount = q2(sub), q2(tax), q2(sub + tax)
