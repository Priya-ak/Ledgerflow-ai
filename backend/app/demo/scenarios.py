"""Synthetic demo data. ALL companies, people, GSTINs and invoices are fictional.

GSTINs are generated with valid check digits from made-up PANs so the format
checks behave realistically; they do not belong to any real taxpayer.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal

from app.services.gst import make_gstin
from app.services.money import ZERO, q2

D = Decimal

BUYER = {
    "name": "Arunachala Engineering Works Pvt Ltd (DEMO)",
    "gstin": make_gstin("33", "AAACA9001K"),
    "address": "12 Industrial Estate Road, Guindy, Chennai, Tamil Nadu 600032",
    "state_code": "33",
    "email": "accounts@arunachala-demo.example",
    "phone": "+91 44 0000 0000",
}

SUPPLIERS = {
    "KST": {"name": "Kaveri Steel Traders", "gstin": make_gstin("33", "AAFFK2001L"), "state": "33",
            "address": "45 Steel Market, Trichy, Tamil Nadu 620001", "email": "billing@kaveri-demo.example",
            "phone": "+91 431 000 0001", "contact": "R. Mani", "terms": 30},
    "DOS": {"name": "Deccan Office Supplies", "gstin": make_gstin("29", "AAGCD3002M"), "state": "29",
            "address": "8 MG Road, Bengaluru, Karnataka 560001", "email": "invoices@deccan-demo.example",
            "phone": "+91 80 000 0002", "contact": "S. Rao", "terms": 15},
    "MLS": {"name": "Malabar Logistics Services", "gstin": make_gstin("32", "AAHFM4003N"), "state": "32",
            "address": "Willingdon Island, Kochi, Kerala 682003", "email": "accounts@malabar-demo.example",
            "phone": "+91 484 000 0003", "contact": "A. Thomas", "terms": 30},
    "CEL": {"name": "Coromandel Electricals", "gstin": make_gstin("33", "AAJFC5004P"), "state": "33",
            "address": "21 Anna Salai, Chennai, Tamil Nadu 600002", "email": "sales@coromandel-demo.example",
            "phone": "+91 44 000 0004", "contact": "K. Priya", "terms": 45},
}


@dataclass
class Line:
    desc: str
    hsn: str
    qty: Decimal
    unit: str
    price: Decimal
    rate: Decimal
    disc: Decimal = ZERO
    tax_override: Decimal | None = None  # deliberately wrong tax (scenario)

    @property
    def taxable(self) -> Decimal:
        return q2(self.qty * self.price - self.disc)

    @property
    def tax(self) -> Decimal:
        return self.tax_override if self.tax_override is not None else q2(self.taxable * self.rate / 100)

    @property
    def total(self) -> Decimal:
        return q2(self.taxable + self.tax)


@dataclass
class Scenario:
    key: str
    title: str
    supplier: str
    number: str | None
    inv_date: date | None
    lines: list[Line]
    po_number: str | None = None
    grand_total_delta: Decimal = ZERO
    hide_buyer_gstin: bool = False
    fmt: str = "pdf"  # pdf | png | jpg (scanned)
    description: str = ""
    expected: dict = field(default_factory=dict)

    @property
    def intra(self) -> bool:
        return SUPPLIERS[self.supplier]["state"] == BUYER["state_code"]

    def totals(self) -> dict:
        sub = q2(sum((l.qty * l.price for l in self.lines), ZERO))
        disc = q2(sum((l.disc for l in self.lines), ZERO))
        taxable = q2(sum((l.taxable for l in self.lines), ZERO))
        tax = q2(sum((l.tax for l in self.lines), ZERO))
        cgst = sgst = igst = ZERO
        if self.intra:
            cgst = q2(tax / 2)
            sgst = tax - cgst
        else:
            igst = tax
        return {"subtotal": sub, "discount": disc, "taxable": taxable, "cgst": cgst, "sgst": sgst,
                "igst": igst, "tax": tax, "grand": q2(taxable + tax + self.grand_total_delta)}


BASE = date(2026, 10, 1)


def _d(days: int) -> date:
    return BASE + timedelta(days=days)


SCENARIOS: list[Scenario] = [
    Scenario("01_valid", "Valid invoice (intra-state CGST/SGST, PO matched)", "KST", "KST/26-27/0412", _d(3),
             [Line("MS Hex Bolt M12 x 50", "7318", D("500"), "Nos", D("14.50"), D("18")),
              Line("Steel Flat Washer M12", "7318", D("500"), "Nos", D("2.20"), D("18")),
              Line("MS Angle 50x50x6 mm", "7216", D("120"), "Kg", D("68.00"), D("18"), disc=D("160.00"))],
             po_number="PO-2026-0101", description="All arithmetic, GST and PO quantities agree.",
             expected={"validation": "passed", "po": "matched"}),
    Scenario("02_wrong_gst", "Incorrect GST calculation (inter-state IGST)", "DOS", "DOS-INV-88213", _d(5),
             [Line("A4 Copier Paper 75 GSM (Box of 5)", "4802", D("40"), "Box", D("1250.00"), D("12")),
              Line("Ergonomic Office Chair", "9401", D("4"), "Nos", D("8900.00"), D("18"), tax_override=D("4272.00"))],
             po_number="PO-2026-0102", description="Chair line charges 12% tax while stating 18%.",
             expected={"validation": "failed"}),
    Scenario("03_arith_mismatch", "Arithmetic mismatch in grand total", "MLS", "MLS/2026/1187", _d(7),
             [Line("Container Freight Chennai-Kochi", "9965", D("2"), "Trip", D("42000.00"), D("5")),
              Line("Loading & Unloading Charges", "9967", D("2"), "Trip", D("3500.00"), D("18"))],
             grand_total_delta=D("500.00"), description="Grand total is overstated by 500.00.",
             expected={"validation": "failed"}),
    Scenario("04_missing_fields", "Scanned image with missing fields", "CEL", None, None,
             [Line("LED Panel Light 18W", "9405", D("60"), "Nos", D("640.00"), D("18"))],
             hide_buyer_gstin=True, fmt="png", description="No invoice number, date or buyer GSTIN printed; processed via OCR.",
             expected={"validation": "failed"}),
    Scenario("05_duplicate", "Duplicate of the valid invoice", "KST", "KST/26-27/0412", _d(3),
             [Line("MS Hex Bolt M12 x 50", "7318", D("500"), "Nos", D("14.50"), D("18")),
              Line("Steel Flat Washer M12", "7318", D("500"), "Nos", D("2.20"), D("18")),
              Line("MS Angle 50x50x6 mm", "7216", D("120"), "Kg", D("68.00"), D("18"), disc=D("160.00"))],
             po_number="PO-2026-0101", description="Same supplier, number, date and amount as scenario 01.",
             expected={"duplicate": "duplicate"}),
    Scenario("06_po_mismatch", "Purchase-order price and quantity mismatch", "CEL", "CE-24518", _d(9),
             [Line("Copper Cable 4 sq mm (90 m coil)", "8544", D("12"), "Coil", D("5150.00"), D("18")),
              Line("MCB 32A Double Pole", "8536", D("30"), "Nos", D("410.00"), D("18"))],
             po_number="PO-2026-0106", description="Unit price above PO and more coils than ordered.",
             expected={"po": "mismatch"}),
    Scenario("07_extra_items", "Invoice with extra line items not on PO", "KST", "KST/26-27/0457", _d(12),
             [Line("MS Hex Bolt M12 x 50", "7318", D("300"), "Nos", D("14.50"), D("18")),
              Line("Galvanised Chain Link 6 mm", "7315", D("40"), "Mtr", D("185.00"), D("18")),
              Line("Delivery Pallets", "4415", D("4"), "Nos", D("750.00"), D("12"))],
             po_number="PO-2026-0107", description="Two items were not ordered on the PO.",
             expected={"po": "partially_matched"}),
    Scenario("08_needs_review", "Low-quality scan requiring human review", "DOS", "DOS-INV-88390", _d(15),
             [Line("Toner Cartridge 12A Compatible", "8443", D("10"), "Nos", D("1850.00"), D("18")),
              Line("Whiteboard Marker (Pack of 10)", "9608", D("15"), "Pack", D("320.00"), D("18"))],
             fmt="jpg", description="Skewed, noisy JPEG scan; OCR output must be checked by a person.",
             expected={"needs_review": True}),
]

PURCHASE_ORDERS = [
    {"po_number": "PO-2026-0101", "supplier": "KST", "days": -10, "lines": SCENARIOS[0].lines},
    {"po_number": "PO-2026-0102", "supplier": "DOS", "days": -8, "lines": [
        Line("A4 Copier Paper 75 GSM (Box of 5)", "4802", D("40"), "Box", D("1250.00"), D("12")),
        Line("Ergonomic Office Chair", "9401", D("4"), "Nos", D("8900.00"), D("18"))]},
    {"po_number": "PO-2026-0106", "supplier": "CEL", "days": -6, "lines": [
        Line("Copper Cable 4 sq mm (90 m coil)", "8544", D("10"), "Coil", D("4980.00"), D("18")),
        Line("MCB 32A Double Pole", "8536", D("30"), "Nos", D("410.00"), D("18"))]},
    {"po_number": "PO-2026-0107", "supplier": "KST", "days": -4, "lines": [
        Line("MS Hex Bolt M12 x 50", "7318", D("300"), "Nos", D("14.50"), D("18"))]},
]
