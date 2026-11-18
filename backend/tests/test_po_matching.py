from decimal import Decimal as D

from app.demo.scenarios import PURCHASE_ORDERS, SCENARIOS
from app.services.po_matching import Tolerances, match_lines


class L:
    def __init__(self, l):
        self.description, self.hsn_sac, self.quantity, self.unit_price = l.desc, l.hsn, l.qty, l.price
        self.tax_rate, self.taxable_value, self.line_total = l.rate, l.taxable, l.total


def _run(sc_idx, po_idx, supplier_ok=True):
    inv = [L(l) for l in SCENARIOS[sc_idx].lines]
    po = [L(l) for l in PURCHASE_ORDERS[po_idx]["lines"]]
    return match_lines(inv, po, Tolerances(), supplier_ok)


def test_exact_match_with_discount():
    assert _run(0, 0)["status"] == "matched"


def test_price_and_quantity_mismatch():
    r = _run(5, 2)
    assert r["status"] == "mismatch"
    fields = {d["field"] for d in r["matched_items"][0]["differences"]}
    assert {"quantity", "unit_price", "amount"} <= fields


def test_extra_items_partially_matched():
    r = _run(6, 3)
    assert r["status"] == "partially_matched"
    assert len(r["extra_items"]) == 2 and not r["missing_items"]


def test_supplier_mismatch():
    assert _run(0, 0, supplier_ok=False)["status"] == "mismatch"


def test_price_within_tolerance_is_matched():
    inv = [L(l) for l in SCENARIOS[0].lines]
    inv[0].unit_price = inv[0].unit_price * D("1.01")
    po = [L(l) for l in PURCHASE_ORDERS[0]["lines"]]
    assert match_lines(inv, po, Tolerances(price_pct=D("2"), amount=D("100")), True)["status"] == "matched"
