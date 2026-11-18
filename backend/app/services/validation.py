"""Deterministic financial validation engine.

Pure functions over Decimal values. No LLM is involved in any calculation or
decision here. The engine never modifies invoice values; it only reports.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal

from app.services.gst import STATE_CODES, normalize_gstin, validate_gstin
from app.services.money import ZERO, fmt, q2

GST_START = date(2017, 7, 1)
STANDARD_GST_RATES = {Decimal(r) for r in ("0", "0.1", "0.25", "1.5", "3", "5", "12", "18", "28")}

CRITICAL, WARNING, INFO = "critical", "warning", "info"


@dataclass
class LineInput:
    line_no: int
    description: str | None = None
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    discount: Decimal | None = None
    taxable_value: Decimal | None = None
    tax_rate: Decimal | None = None
    tax_amount: Decimal | None = None
    line_total: Decimal | None = None


@dataclass
class InvoiceInput:
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    supplier_id: str | None = None
    supplier_name: str | None = None
    supplier_gstin: str | None = None
    buyer_gstin: str | None = None
    subtotal: Decimal | None = None
    discount: Decimal | None = None
    taxable_amount: Decimal | None = None
    cgst: Decimal | None = None
    sgst: Decimal | None = None
    igst: Decimal | None = None
    other_charges: Decimal | None = None
    total_tax: Decimal | None = None
    grand_total: Decimal | None = None
    items: list[LineInput] = field(default_factory=list)


@dataclass
class ValidationContext:
    amount_tolerance: Decimal = Decimal("1.00")
    line_tolerance: Decimal = Decimal("0.05")
    today: date | None = None
    supplier_master_gstin: str | None = None
    supplier_master_status: str | None = None
    duplicate_status: str | None = None
    po_match_status: str | None = None


@dataclass
class Check:
    code: str
    name: str
    severity: str
    passed: bool
    explanation: str
    expected: str | None = None
    actual: str | None = None
    difference: str | None = None
    recommended_action: str | None = None
    line_no: int | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items()}


class _Collector:
    def __init__(self) -> None:
        self.checks: list[Check] = []

    def add(self, **kw) -> None:
        self.checks.append(Check(**kw))

    def compare(self, code: str, name: str, expected: Decimal, actual: Decimal | None, tol: Decimal,
                severity: str, ok_msg: str, fail_msg: str, action: str, line_no: int | None = None) -> None:
        if actual is None:
            self.add(code=code, name=name, severity=WARNING, passed=False, line_no=line_no,
                     expected=fmt(expected), explanation=f"{name}: value is missing, cannot verify.",
                     recommended_action="Enter the value printed on the invoice.")
            return
        diff = q2(actual - expected)
        ok = abs(diff) <= tol
        self.add(code=code, name=name, severity=severity, passed=ok, line_no=line_no,
                 expected=fmt(expected), actual=fmt(actual), difference=fmt(diff),
                 explanation=ok_msg if ok else f"{fail_msg} (difference {fmt(diff)}, tolerance {fmt(tol)}).",
                 recommended_action=None if ok else action)


def _sum(values) -> Decimal:
    return sum((v for v in values if v is not None), ZERO)


def validate_invoice(inv: InvoiceInput, ctx: ValidationContext | None = None) -> dict:
    ctx = ctx or ValidationContext()
    today = ctx.today or datetime.now(timezone.utc).date()
    tol, ltol = ctx.amount_tolerance, ctx.line_tolerance
    c = _Collector()

    # 1. Required fields --------------------------------------------------
    required = {
        "invoice_number": inv.invoice_number, "invoice_date": inv.invoice_date,
        "supplier": inv.supplier_id or inv.supplier_name, "grand_total": inv.grand_total,
    }
    missing = [k for k, v in required.items() if v in (None, "")]
    c.add(code="required_fields", name="Required fields present", severity=CRITICAL, passed=not missing,
          actual=", ".join(missing) or None,
          explanation="All required fields are present." if not missing else f"Missing required fields: {', '.join(missing)}.",
          recommended_action=None if not missing else "Review the original document and fill the missing fields.")
    if not inv.items:
        c.add(code="line_items_present", name="Line items present", severity=WARNING, passed=False,
              explanation="No line items were captured, so line-level checks were skipped.",
              recommended_action="Add the invoice line items from the original document.")

    # 2. Dates ---------------------------------------------------------------
    if inv.invoice_date:
        future = inv.invoice_date > today
        c.add(code="invoice_date_not_future", name="Invoice date is not in the future", severity=CRITICAL,
              passed=not future, actual=inv.invoice_date.isoformat(), expected=f"<= {today.isoformat()}",
              explanation="Invoice date is valid." if not future else "Invoice date is in the future.",
              recommended_action=None if not future else "Check the invoice date for typos or OCR errors.")
        if inv.invoice_date < GST_START:
            c.add(code="invoice_date_gst_era", name="Invoice date within GST era", severity=WARNING, passed=False,
                  actual=inv.invoice_date.isoformat(), explanation="Invoice predates GST (1 July 2017).",
                  recommended_action="Confirm the date; pre-GST invoices follow different tax rules.")
    if inv.invoice_date and inv.due_date:
        ok = inv.due_date >= inv.invoice_date
        c.add(code="due_date_order", name="Due date on or after invoice date", severity=WARNING, passed=ok,
              actual=inv.due_date.isoformat(), expected=f">= {inv.invoice_date.isoformat()}",
              explanation="Due date is consistent." if ok else "Due date is before the invoice date.",
              recommended_action=None if ok else "Correct the due date.")

    # 3. GSTIN format checks ---------------------------------------------------
    sup_ok, sup_msg = validate_gstin(inv.supplier_gstin)
    c.add(code="supplier_gstin_format", name="Supplier GSTIN format", severity=WARNING if not inv.supplier_gstin else CRITICAL,
          passed=sup_ok, actual=normalize_gstin(inv.supplier_gstin), explanation=sup_msg,
          recommended_action=None if sup_ok else "Verify the supplier GSTIN against the document and supplier master.")
    buy_ok, buy_msg = validate_gstin(inv.buyer_gstin)
    c.add(code="buyer_gstin_format", name="Buyer GSTIN format", severity=WARNING, passed=buy_ok,
          actual=normalize_gstin(inv.buyer_gstin), explanation=buy_msg,
          recommended_action=None if buy_ok else "Verify the buyer (your company) GSTIN printed on the invoice.")

    # 4/5. Line items -------------------------------------------------------
    for it in inv.items:
        if it.quantity is not None and it.quantity <= 0:
            c.add(code="line_quantity_positive", name="Quantity is positive", severity=CRITICAL, passed=False,
                  line_no=it.line_no, actual=str(it.quantity), explanation=f"Line {it.line_no}: quantity must be greater than zero.",
                  recommended_action="Correct the quantity.")
        if it.unit_price is not None and it.unit_price < 0:
            c.add(code="line_price_non_negative", name="Unit price is not negative", severity=CRITICAL, passed=False,
                  line_no=it.line_no, actual=fmt(it.unit_price), explanation=f"Line {it.line_no}: negative unit price.",
                  recommended_action="Correct the unit price; credits belong on a credit note.")
        if it.tax_rate is not None and it.tax_rate not in STANDARD_GST_RATES:
            c.add(code="line_tax_rate_standard", name="Standard GST rate", severity=WARNING, passed=False,
                  line_no=it.line_no, actual=f"{it.tax_rate}%", explanation=f"Line {it.line_no}: {it.tax_rate}% is not a standard GST slab.",
                  recommended_action="Confirm the GST rate for this HSN/SAC code.")
        if it.quantity is not None and it.unit_price is not None:
            expected_taxable = q2(it.quantity * it.unit_price - (it.discount or ZERO))
            c.compare("line_taxable", "Line taxable value", expected_taxable, it.taxable_value, ltol, CRITICAL,
                      f"Line {it.line_no}: taxable value matches qty x price - discount.",
                      f"Line {it.line_no}: taxable value does not equal qty x price - discount",
                      "Check quantity, unit price and discount on this line.", it.line_no)
        base = it.taxable_value
        if base is not None and it.tax_rate is not None:
            c.compare("line_tax", "Line tax amount", q2(base * it.tax_rate / 100), it.tax_amount, ltol, CRITICAL,
                      f"Line {it.line_no}: tax equals taxable value x rate.",
                      f"Line {it.line_no}: tax amount does not equal taxable value x {it.tax_rate}%",
                      "Verify the GST rate and tax amount on this line.", it.line_no)
        if base is not None and it.tax_amount is not None:
            c.compare("line_total", "Line total", q2(base + it.tax_amount), it.line_total, ltol, CRITICAL,
                      f"Line {it.line_no}: total equals taxable value + tax.",
                      f"Line {it.line_no}: line total does not equal taxable value + tax",
                      "Verify the line total.", it.line_no)

    # 6. Summary arithmetic ---------------------------------------------------
    items = inv.items
    if items:
        gross = q2(_sum(i.quantity * i.unit_price for i in items if i.quantity is not None and i.unit_price is not None))
        line_taxable = q2(_sum(i.taxable_value for i in items))
        if inv.subtotal is not None:
            # Some suppliers print subtotal before discounts, others after - accept either.
            candidates = [gross, line_taxable]
            best = min(candidates, key=lambda x: abs(inv.subtotal - x))
            c.compare("subtotal", "Subtotal", best, inv.subtotal, tol, CRITICAL,
                      "Subtotal matches the sum of line items.", "Subtotal does not match the sum of line items",
                      "Recalculate the subtotal from the line items.")
        if inv.taxable_amount is not None:
            c.compare("taxable_total", "Taxable amount", line_taxable, inv.taxable_amount, tol, CRITICAL,
                      "Taxable amount matches the sum of line taxable values.",
                      "Taxable amount does not match the sum of line taxable values",
                      "Check discounts and line taxable values.")
        if inv.subtotal is not None and inv.taxable_amount is not None and inv.discount is not None:
            c.compare("discount", "Discount", q2(inv.subtotal - inv.taxable_amount), inv.discount, tol, WARNING,
                      "Discount is consistent with subtotal and taxable amount.",
                      "Discount is inconsistent with subtotal minus taxable amount",
                      "Confirm the discount amount.")
        line_tax = q2(_sum(i.tax_amount for i in items))
        header_tax = q2(_sum([inv.cgst, inv.sgst, inv.igst]))
        if any(v is not None for v in (inv.cgst, inv.sgst, inv.igst)):
            c.compare("tax_total", "Total GST", line_tax, header_tax, tol, CRITICAL,
                      "CGST + SGST + IGST matches the sum of line taxes.",
                      "CGST + SGST + IGST does not match the sum of line taxes",
                      "Verify each GST component against the line items.")
        if inv.grand_total is not None:
            line_totals = q2(_sum(i.line_total for i in items)) + (inv.other_charges or ZERO)
            if any(i.line_total is not None for i in items):
                c.compare("grand_total_vs_lines", "Grand total vs line totals", line_totals, inv.grand_total, tol, CRITICAL,
                          "Grand total matches the line totals plus other charges.",
                          "Grand total does not match line totals plus other charges",
                          "Check for missing lines, other charges or a wrong grand total.")

    if inv.grand_total is not None and inv.taxable_amount is not None:
        tax = inv.total_tax if inv.total_tax is not None else q2(_sum([inv.cgst, inv.sgst, inv.igst]))
        expected = q2(inv.taxable_amount + tax + (inv.other_charges or ZERO))
        c.compare("grand_total", "Grand total", expected, inv.grand_total, tol, CRITICAL,
                  "Grand total equals taxable amount + tax + other charges.",
                  "Grand total does not equal taxable amount + tax + other charges",
                  "Recalculate the grand total.")
    if inv.total_tax is not None and any(v is not None for v in (inv.cgst, inv.sgst, inv.igst)):
        c.compare("total_tax_components", "Total tax equals components", q2(_sum([inv.cgst, inv.sgst, inv.igst])),
                  inv.total_tax, tol, WARNING, "Total tax equals CGST + SGST + IGST.",
                  "Total tax does not equal CGST + SGST + IGST", "Correct the total tax.")

    # 7. GST regime (intra-state CGST+SGST vs inter-state IGST) ---------------
    if sup_ok and buy_ok:
        s_state, b_state = normalize_gstin(inv.supplier_gstin)[:2], normalize_gstin(inv.buyer_gstin)[:2]
        cg, sg, ig = inv.cgst or ZERO, inv.sgst or ZERO, inv.igst or ZERO
        if s_state == b_state:
            ok = ig == ZERO and abs(cg - sg) <= ltol
            c.add(code="gst_regime", name="GST regime (intra-state)", severity=CRITICAL, passed=ok,
                  expected="CGST = SGST, IGST = 0", actual=f"CGST {fmt(cg)}, SGST {fmt(sg)}, IGST {fmt(ig)}",
                  explanation=(f"Intra-state supply within {STATE_CODES.get(s_state, s_state)}: CGST/SGST applied correctly." if ok
                               else f"Supplier and buyer are both in {STATE_CODES.get(s_state, s_state)}; expected equal CGST and SGST with no IGST."),
                  recommended_action=None if ok else "Confirm place of supply; request a corrected invoice if GST type is wrong.")
        else:
            ok = cg == ZERO and sg == ZERO
            c.add(code="gst_regime", name="GST regime (inter-state)", severity=CRITICAL, passed=ok,
                  expected="IGST only", actual=f"CGST {fmt(cg)}, SGST {fmt(sg)}, IGST {fmt(ig)}",
                  explanation=("Inter-state supply: IGST applied correctly." if ok
                               else "Supplier and buyer are in different states; expected IGST, not CGST/SGST."),
                  recommended_action=None if ok else "Confirm place of supply; request a corrected invoice if GST type is wrong.")

    # 8. Supplier consistency -------------------------------------------------
    if inv.supplier_id is None:
        c.add(code="supplier_linked", name="Supplier matched to master data", severity=WARNING, passed=False,
              actual=inv.supplier_name, explanation="Invoice is not linked to a supplier record.",
              recommended_action="Select an existing supplier or create a new one.")
    elif ctx.supplier_master_gstin:
        m, p = normalize_gstin(ctx.supplier_master_gstin), normalize_gstin(inv.supplier_gstin)
        ok = m == p
        c.add(code="supplier_gstin_consistent", name="Supplier GSTIN matches master data", severity=WARNING, passed=ok,
              expected=m, actual=p,
              explanation="Printed GSTIN matches the supplier record." if ok else "Printed GSTIN differs from the supplier record.",
              recommended_action=None if ok else "Confirm the supplier identity before approving.")
    elif inv.supplier_gstin:
        c.add(code="supplier_gstin_consistent", name="Supplier GSTIN on master data", severity=INFO, passed=False,
              actual=normalize_gstin(inv.supplier_gstin), explanation="The supplier record has no GSTIN to compare against.",
              recommended_action="Add the GSTIN to the supplier record.")
    if ctx.supplier_master_status and ctx.supplier_master_status != "active":
        c.add(code="supplier_active", name="Supplier is active", severity=WARNING, passed=False,
              actual=ctx.supplier_master_status, explanation=f"Supplier status is '{ctx.supplier_master_status}'.",
              recommended_action="Confirm this supplier should still be paid.")

    # 9. Cross-module results ---------------------------------------------------
    if ctx.duplicate_status in ("duplicate", "possible_duplicate"):
        exact = ctx.duplicate_status == "duplicate"
        c.add(code="duplicate", name="Duplicate check", severity=CRITICAL if exact else WARNING, passed=False,
              actual=ctx.duplicate_status,
              explanation="This invoice duplicates an existing invoice." if exact else "This invoice may duplicate an existing invoice.",
              recommended_action="Investigate the matching invoice and resolve the duplicate warning.")
    elif ctx.duplicate_status:
        c.add(code="duplicate", name="Duplicate check", severity=INFO, passed=True, actual=ctx.duplicate_status,
              explanation="No unresolved duplicate detected.")
    if ctx.po_match_status in ("mismatch", "partially_matched", "requires_review"):
        c.add(code="po_match", name="Purchase-order match", severity=WARNING, passed=False, actual=ctx.po_match_status,
              explanation="Invoice does not fully match its purchase order.",
              recommended_action="Review the PO comparison before approval.")
    elif ctx.po_match_status in ("matched", "no_po_found"):
        c.add(code="po_match", name="Purchase-order match", severity=INFO, passed=ctx.po_match_status == "matched",
              actual=ctx.po_match_status,
              explanation="Invoice matches its purchase order." if ctx.po_match_status == "matched" else "No purchase order referenced.")

    failed = [ch for ch in c.checks if not ch.passed]
    critical = [ch for ch in failed if ch.severity == CRITICAL]
    warnings = [ch for ch in failed if ch.severity == WARNING]
    status = "failed" if critical else ("warnings" if warnings else "passed")
    return {
        "status": status,
        "has_critical_errors": bool(critical),
        "summary": {"total": len(c.checks), "passed": len(c.checks) - len(failed),
                    "critical_failures": len(critical), "warnings": len(warnings)},
        "tolerance": {"amount": fmt(tol), "line": fmt(ltol)},
        "checks": [ch.as_dict() for ch in c.checks],
        "engine": "deterministic-decimal-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
