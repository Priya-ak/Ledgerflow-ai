"""Deterministic invoice <-> purchase-order matching (2-way match).

Lines are paired by HSN/SAC code and description similarity. All differences
are calculated with Decimal and compared against configurable tolerances.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from difflib import SequenceMatcher

from app.models.enums import PoMatchStatus
from app.services.money import ZERO, fmt, q2


@dataclass
class Tolerances:
    price_pct: Decimal = Decimal("2.00")
    qty_pct: Decimal = Decimal("0.00")
    amount: Decimal = Decimal("1.00")


def _sim(a: str | None, b: str | None) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _pct_diff(actual: Decimal, expected: Decimal) -> Decimal:
    if expected == 0:
        return Decimal("0") if actual == 0 else Decimal("100")
    return q2(abs(actual - expected) / expected * 100)


def match_lines(inv_items: list, po_items: list, tol: Tolerances, supplier_ok: bool) -> dict:
    """inv_items / po_items: objects with description, hsn_sac, quantity, unit_price, tax_rate, line_total/taxable."""
    pairs = []
    used: set[int] = set()
    for ii, it in enumerate(inv_items):
        best, best_score = None, 0.0
        for pi, po in enumerate(po_items):
            if pi in used:
                continue
            s = _sim(it.description, po.description)
            if it.hsn_sac and po.hsn_sac and it.hsn_sac == po.hsn_sac:
                s += 0.35
            if s > best_score:
                best, best_score = pi, s
        if best is not None and best_score >= 0.6:
            used.add(best)
            pairs.append((ii, best, round(best_score, 2)))

    matched, issues = [], []
    paired_inv = {p[0] for p in pairs}
    for ii, pi, score in pairs:
        it, po = inv_items[ii], po_items[pi]
        diffs = []
        if it.quantity is not None and _pct_diff(it.quantity, po.quantity) > tol.qty_pct:
            diffs.append({"field": "quantity", "invoice": str(it.quantity), "po": str(po.quantity),
                          "difference": str(it.quantity - po.quantity)})
        if it.unit_price is not None and _pct_diff(it.unit_price, po.unit_price) > tol.price_pct:
            diffs.append({"field": "unit_price", "invoice": fmt(it.unit_price), "po": fmt(po.unit_price),
                          "difference": fmt(it.unit_price - po.unit_price)})
        if it.tax_rate is not None and it.tax_rate != po.tax_rate:
            diffs.append({"field": "tax_rate", "invoice": str(it.tax_rate), "po": str(po.tax_rate),
                          "difference": str(it.tax_rate - po.tax_rate)})
        if it.hsn_sac and po.hsn_sac and it.hsn_sac != po.hsn_sac:
            diffs.append({"field": "hsn_sac", "invoice": it.hsn_sac, "po": po.hsn_sac, "difference": None})
        # Compare gross value (qty x price) on both sides; supplier discounts are not PO variances.
        inv_amt = (q2(it.quantity * it.unit_price) if it.quantity is not None and it.unit_price is not None
                   else it.taxable_value)
        po_amt = q2(po.quantity * po.unit_price)
        if inv_amt is not None and abs(inv_amt - po_amt) > tol.amount:
            diffs.append({"field": "amount", "invoice": fmt(inv_amt), "po": fmt(po_amt), "difference": fmt(inv_amt - po_amt)})
        matched.append({"invoice_line": ii + 1, "po_line": pi + 1, "description": it.description,
                        "po_description": po.description, "similarity": score, "differences": diffs,
                        "status": "matched" if not diffs else "mismatch"})
        if diffs:
            issues.append(f"Line {ii + 1} ({it.description}): " + ", ".join(d["field"] for d in diffs) + " differ from PO.")

    extra = [{"invoice_line": i + 1, "description": it.description, "amount": fmt(it.line_total)}
             for i, it in enumerate(inv_items) if i not in paired_inv]
    missing = [{"po_line": i + 1, "description": po.description, "quantity": str(po.quantity)}
               for i, po in enumerate(po_items) if i not in used]
    for e in extra:
        issues.append(f"Invoice line {e['invoice_line']} ({e['description']}) is not on the PO.")
    for m in missing:
        issues.append(f"PO line {m['po_line']} ({m['description']}) was not invoiced.")
    if not supplier_ok:
        issues.insert(0, "Invoice supplier differs from the PO supplier.")

    any_diff = any(m["differences"] for m in matched)
    if not supplier_ok or (matched and all(m["differences"] for m in matched)) or not matched:
        status = PoMatchStatus.MISMATCH
    elif any_diff:
        status = PoMatchStatus.MISMATCH if not (extra or missing) else PoMatchStatus.PARTIALLY_MATCHED
    elif extra or missing:
        status = PoMatchStatus.PARTIALLY_MATCHED
    else:
        status = PoMatchStatus.MATCHED
    return {"status": str(status), "supplier_matches": supplier_ok, "matched_items": matched,
            "extra_items": extra, "missing_items": missing, "issues": issues,
            "tolerances": {"price_pct": fmt(tol.price_pct), "qty_pct": fmt(tol.qty_pct), "amount": fmt(tol.amount)}}


def compare_totals(inv_total: Decimal | None, po_total: Decimal, tol: Tolerances) -> dict:
    if inv_total is None:
        return {"invoice": None, "po": fmt(po_total), "difference": None, "within_tolerance": False}
    diff = q2(inv_total - po_total)
    return {"invoice": fmt(inv_total), "po": fmt(po_total), "difference": fmt(diff),
            "within_tolerance": abs(diff) <= tol.amount, "exceeds_po": diff > tol.amount}
