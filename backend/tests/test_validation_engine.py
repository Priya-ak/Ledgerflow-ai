from datetime import date
from decimal import Decimal as D

from app.demo.scenarios import BUYER, SUPPLIERS
from app.services.gst import gstin_check_digit, make_gstin, validate_gstin
from app.services.money import to_decimal
from app.services.validation import InvoiceInput, LineInput, ValidationContext, validate_invoice

CTX = ValidationContext(today=date(2026, 11, 1))


def _line(n=1, qty="10", price="100.00", disc="0", rate="18", **over):
    qty, price, disc, rate = D(qty), D(price), D(disc), D(rate)
    taxable = qty * price - disc
    tax = (taxable * rate / 100).quantize(D("0.01"))
    vals = dict(line_no=n, description="Item", quantity=qty, unit_price=price, discount=disc, taxable_value=taxable,
                tax_rate=rate, tax_amount=tax, line_total=taxable + tax)
    vals.update(over)
    return LineInput(**vals)


def _inv(lines, supplier="KST", **over):
    taxable = sum(l.taxable_value for l in lines)
    tax = sum(l.tax_amount for l in lines)
    intra = SUPPLIERS[supplier]["state"] == "33"
    vals = dict(invoice_number="INV-1", invoice_date=date(2026, 10, 1), due_date=date(2026, 10, 31), supplier_id="s1",
                supplier_name="Sup", supplier_gstin=SUPPLIERS[supplier]["gstin"], buyer_gstin=BUYER["gstin"],
                subtotal=sum(l.quantity * l.unit_price for l in lines), discount=sum(l.discount for l in lines),
                taxable_amount=taxable, cgst=tax / 2 if intra else D(0), sgst=tax / 2 if intra else D(0),
                igst=D(0) if intra else tax, total_tax=tax, grand_total=taxable + tax, items=lines)
    vals.update(over)
    return InvoiceInput(**vals)


def failed(report):
    return {c["code"] for c in report["checks"] if not c["passed"] and c["severity"] != "info"}


def test_valid_intra_state_invoice_passes():
    r = validate_invoice(_inv([_line(), _line(2, "5", "40.50", disc="2.50")]), CTX)
    assert r["status"] == "passed", failed(r)
    assert not r["has_critical_errors"]


def test_valid_inter_state_igst_passes():
    r = validate_invoice(_inv([_line()], supplier="DOS"), CTX)
    assert r["status"] == "passed", failed(r)


def test_wrong_line_tax_is_critical_with_expected_actual_difference():
    bad = _line(tax_amount=D("120.00"), line_total=D("1120.00"))
    r = validate_invoice(_inv([bad]), CTX)
    assert r["status"] == "failed"
    chk = next(c for c in r["checks"] if c["code"] == "line_tax")
    assert (chk["expected"], chk["actual"], chk["difference"]) == ("180.00", "120.00", "-60.00")
    assert chk["recommended_action"]


def test_grand_total_arithmetic_mismatch():
    inv = _inv([_line()])
    inv.grand_total += D("500")
    assert {"grand_total", "grand_total_vs_lines"} <= failed(validate_invoice(inv, CTX))


def test_tolerance_absorbs_round_off():
    inv = _inv([_line()])
    inv.grand_total += D("0.40")
    assert validate_invoice(inv, CTX)["status"] == "passed"


def test_missing_required_fields():
    r = validate_invoice(_inv([_line()], invoice_number=None, invoice_date=None), CTX)
    chk = next(c for c in r["checks"] if c["code"] == "required_fields")
    assert not chk["passed"] and "invoice_number" in chk["actual"]


def test_wrong_gst_regime_intra_state_charged_igst():
    l = _line()
    inv = _inv([l], cgst=D(0), sgst=D(0), igst=l.tax_amount)
    assert "gst_regime" in failed(validate_invoice(inv, CTX))


def test_wrong_gst_regime_inter_state_charged_cgst_sgst():
    l = _line()
    inv = _inv([l], supplier="DOS", cgst=l.tax_amount / 2, sgst=l.tax_amount / 2, igst=D(0))
    assert "gst_regime" in failed(validate_invoice(inv, CTX))


def test_future_date_and_due_before_invoice():
    r = validate_invoice(_inv([_line()], invoice_date=date(2027, 1, 1), due_date=date(2026, 12, 1)), CTX)
    assert {"invoice_date_not_future", "due_date_order"} <= failed(r)


def test_negative_quantity_is_critical():
    r = validate_invoice(_inv([_line(qty="-2")]), CTX)
    assert "line_quantity_positive" in failed(r)
    assert r["has_critical_errors"]


def test_invalid_supplier_gstin_checksum():
    g = SUPPLIERS["KST"]["gstin"]
    bad = g[:-1] + ("A" if g[-1] != "A" else "B")
    assert "supplier_gstin_format" in failed(validate_invoice(_inv([_line()], supplier_gstin=bad), CTX))


def test_supplier_master_gstin_mismatch_warns():
    ctx = ValidationContext(today=date(2026, 11, 1), supplier_master_gstin=SUPPLIERS["CEL"]["gstin"])
    r = validate_invoice(_inv([_line()]), ctx)
    assert "supplier_gstin_consistent" in failed(r) and r["status"] == "warnings"


def test_duplicate_context_is_critical():
    ctx = ValidationContext(today=date(2026, 11, 1), duplicate_status="duplicate")
    assert validate_invoice(_inv([_line()]), ctx)["status"] == "failed"


def test_engine_never_mutates_input():
    inv = _inv([_line()])
    before = (inv.grand_total, inv.items[0].tax_amount)
    validate_invoice(inv, CTX)
    assert (inv.grand_total, inv.items[0].tax_amount) == before


def test_gstin_helpers():
    g = make_gstin("33", "ABCDE1234F")
    assert validate_gstin(g)[0]
    assert g[-1] == gstin_check_digit(g[:14])
    assert not validate_gstin("99ABCDE1234F1Z5")[0]  # unknown state
    assert not validate_gstin("33ABCDE1234F1Z")[0]  # too short


def test_decimal_parsing():
    assert to_decimal("1,23,456.70") == D("123456.70")
    assert to_decimal("Rs. 1,200") == D("1200")
    assert to_decimal("(50.00)") == D("-50.00")
    assert to_decimal("abc") is None
