"""Seed a complete, clearly-labelled DEMO workspace.

Invoices for the 8 scenarios are produced by running the REAL pipeline
(storage -> PyMuPDF/Tesseract -> rule extraction -> validation) on the synthetic
documents in sample-data/. Historical invoices used for dashboard trends are
entered as manual demo records (extraction_method="manual-demo").

Usage:  python -m app.demo.seed            (refuses if demo data already exists)
        python -m app.demo.seed --reset    (SQLite only: wipes the local DB first)
"""
from __future__ import annotations

import argparse
import hashlib
import random
import sys
import tempfile
from datetime import datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.demo.scenarios import BUYER, PURCHASE_ORDERS, SCENARIOS, SUPPLIERS, Line
from app.models import (
    ApprovalPolicy, Company, CompanySettings, Document, Invoice, InvoiceItem, PurchaseOrder, PurchaseOrderItem, Supplier, User,
)
from app.models.base import new_id
from app.models.enums import Role
from app.services import approvals, audit
from app.services.duplicates import normalize_invoice_number
from app.services.file_types import CONTENT_TYPES, sniff
from app.services.invoices import recompute_po_totals, run_checks
from app.services.processing import process_document
from app.services.storage import build_key, get_storage

DEMO_PASSWORD = "LedgerFlow2026"  # demo-only credential, documented in README
DEMO_USERS = [
    ("admin@ledgerflow-demo.example", "Meera Iyer (Demo Admin)", Role.ADMIN),
    ("accountant@ledgerflow-demo.example", "Arjun Kumar (Demo Accountant)", Role.ACCOUNTANT),
    ("approver@ledgerflow-demo.example", "Lakshmi Narayanan (Demo Approver)", Role.APPROVER),
    ("finance.head@ledgerflow-demo.example", "Vikram Shah (Demo Finance Head)", Role.APPROVER),
]


def _reset_sqlite() -> None:
    if not settings.is_sqlite:
        sys.exit("--reset is only allowed for the local SQLite database.")
    db_path = Path(settings.DATABASE_URL.replace("sqlite:///", ""))
    for p in (db_path, Path(f"{db_path}-wal"), Path(f"{db_path}-shm")):
        p.unlink(missing_ok=True)
    from alembic import command
    from alembic.config import Config
    cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[2] / "alembic"))
    command.upgrade(cfg, "head")


def _store(db, company_id: str, user_id: str, path: Path) -> Document:
    data = path.read_bytes()
    kind = sniff(data[:16])
    doc_id = new_id()
    key = build_key(company_id, doc_id, "jpg" if kind == "jpeg" else kind)
    get_storage().save(key, path, CONTENT_TYPES[kind])
    doc = Document(id=doc_id, company_id=company_id, uploaded_by_id=user_id, original_filename=path.name,
                   storage_provider=get_storage().name, storage_key=key, content_type=CONTENT_TYPES[kind],
                   size_bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), is_demo=True)
    db.add(doc)
    db.flush()
    return doc


def _historical(db, company, suppliers, accountant, approver, head) -> int:
    """Approved/rejected manual demo invoices over the past 6 months for dashboard trends."""
    rnd = random.Random(42)
    catalogue = {
        "KST": [("MS Round Bar 20 mm", "7214", "Kg", Decimal("72.00"), Decimal("18"), [150, 250, 400, 600, 900])],
        "DOS": [("A4 Copier Paper 75 GSM (Box of 5)", "4802", "Box", Decimal("1250.00"), Decimal("12"), [8, 12, 20, 30])],
        "MLS": [("Road Freight Chennai-Coimbatore", "9965", "Trip", Decimal("18500.00"), Decimal("5"), [1, 2, 3, 5])],
        "CEL": [("LED Panel Light 18W", "9405", "Nos", Decimal("640.00"), Decimal("18"), [20, 40, 60, 120])],
    }
    today = datetime.now(timezone.utc).date()
    n = 0
    for month_back in range(6, 0, -1):
        for code in rnd.sample(list(SUPPLIERS), 3):
            desc, hsn, unit, price, rate, qtys = catalogue[code][0]
            qty = Decimal(rnd.choice(qtys))
            ln = Line(desc, hsn, qty, unit, price, rate)
            d = (today.replace(day=1) - timedelta(days=30 * month_back - rnd.randint(0, 20)))
            intra = SUPPLIERS[code]["state"] == BUYER["state_code"]
            number = f"{code}-H{d.strftime('%y%m')}-{rnd.randint(100, 999)}"
            inv = Invoice(company_id=company.id, supplier_id=suppliers[code].id, invoice_number=number,
                          invoice_number_normalized=normalize_invoice_number(number), invoice_date=d,
                          due_date=d + timedelta(days=SUPPLIERS[code]["terms"]), currency="INR",
                          supplier_name_raw=SUPPLIERS[code]["name"], supplier_gstin_raw=SUPPLIERS[code]["gstin"],
                          buyer_name=BUYER["name"], buyer_gstin=BUYER["gstin"], subtotal=ln.taxable, discount=Decimal("0.00"),
                          taxable_amount=ln.taxable, cgst=ln.tax / 2 if intra else Decimal("0"), sgst=ln.tax / 2 if intra else Decimal("0"),
                          igst=Decimal("0") if intra else ln.tax, total_tax=ln.tax, grand_total=ln.total, status="draft",
                          extraction_method="manual-demo", needs_review_fields=[], is_demo=True, created_by_id=accountant.id,
                          payment_status=rnd.choice(["paid", "paid", "unpaid"]),
                          items=[InvoiceItem(line_no=1, description=desc, hsn_sac=hsn, quantity=qty, unit=unit,
                                             unit_price=price, discount=Decimal("0"), taxable_value=ln.taxable,
                                             tax_rate=rate, tax_amount=ln.tax, line_total=ln.total)])
            db.add(inv)
            db.flush()
            run_checks(db, inv)
            req = approvals.submit(db, inv, accountant, "Monthly supplier bill (demo history)")
            submitted = datetime.combine(d + timedelta(days=2), time(10, 0), timezone.utc)
            req.created_at = inv.submitted_at = submitted
            db.flush()
            if rnd.random() < 0.85:
                approvals.approve(db, inv, approver, "Checked against delivery note (demo).")
                if inv.status != "approved":  # second level (amount above threshold)
                    approvals.approve(db, inv, head, "Within budget (demo).")
            else:
                approvals.reject(db, inv, approver, "Quantity not received in full (demo).")
            req.completed_at = inv.decided_at = submitted + timedelta(hours=rnd.randint(3, 60))
            for s in req.steps:
                s.created_at = req.completed_at
            n += 1
    return n


def seed(reset: bool = False) -> dict:
    if reset:
        _reset_sqlite()
    db = SessionLocal()
    try:
        if db.scalar(select(Company.id).where(Company.is_demo.is_(True))):
            print("Demo data already exists. Use --reset (SQLite) to recreate it.")
            return {}
        company = Company(name=BUYER["name"], gstin=BUYER["gstin"], address=BUYER["address"], state_code=BUYER["state_code"],
                          email=BUYER["email"], phone=BUYER["phone"], is_demo=True)
        db.add(company)
        db.flush()
        db.add(CompanySettings(company_id=company.id))
        db.add(ApprovalPolicy(company_id=company.id, allow_self_approval=False, allow_critical_override=False, levels=[
            {"level": 1, "name": "Manager approval", "role": "approver", "min_amount": "0"},
            {"level": 2, "name": "Finance head approval", "role": "approver", "min_amount": "75000"},
        ]))
        pw = hash_password(DEMO_PASSWORD)
        users = {}
        for email, name, role in DEMO_USERS:
            u = User(company_id=company.id, email=email, full_name=name, role=role, password_hash=pw)
            db.add(u)
            users[email.split("@")[0]] = u
        db.flush()
        accountant, approver, head = users["accountant"], users["approver"], users["finance.head"]

        suppliers = {}
        for code, s in SUPPLIERS.items():
            sup = Supplier(company_id=company.id, code=code, name=s["name"], gstin=s["gstin"], email=s["email"],
                           phone=s["phone"], address=s["address"], contact_person=s["contact"], payment_terms_days=s["terms"])
            db.add(sup)
            suppliers[code] = sup
        db.flush()

        for p in PURCHASE_ORDERS:
            po = PurchaseOrder(company_id=company.id, supplier_id=suppliers[p["supplier"]].id, po_number=p["po_number"],
                               po_date=SCENARIOS[0].inv_date + timedelta(days=p["days"]), status="open",
                               created_by_id=accountant.id, notes="Demo purchase order")
            po.items = [PurchaseOrderItem(line_no=i, description=l.desc, hsn_sac=l.hsn, quantity=l.qty, unit=l.unit,
                                          unit_price=l.price, tax_rate=l.rate, line_total=0)
                        for i, l in enumerate(p["lines"], 1)]
            recompute_po_totals(po)
            db.add(po)
        db.flush()

        hist = _historical(db, company, suppliers, accountant, approver, head)

        # Real pipeline over synthetic documents.
        docs_dir = Path(__file__).resolve().parents[3] / "sample-data" / "synthetic-invoices"
        if not docs_dir.exists() or len(list(docs_dir.iterdir())) < len(SCENARIOS):
            from app.demo.generate_documents import generate  # needs reportlab (requirements-dev.txt)
            docs_dir = Path(tempfile.mkdtemp())
            generate(docs_dir)
        processed = {}
        for sc in SCENARIOS:
            path = next(p for p in docs_dir.iterdir() if p.stem == sc.key)
            doc = _store(db, company.id, accountant.id, path)
            inv, rec = process_document(db, doc, accountant.id)
            audit.record(db, action="invoice.extract", company_id=company.id, actor=accountant, entity_type="invoice",
                         entity_id=inv.id, meta={"document_id": doc.id, "status": rec.status, "text_method": rec.text_method,
                                                 "scenario": sc.key, "demo": True})
            db.flush()
            processed[sc.key] = inv

        # Workflow states for the demo story.
        inv = processed["01_valid"]
        approvals.submit(db, inv, accountant, "Matches PO-2026-0101 and GRN.")
        approvals.approve(db, inv, approver, "Verified against goods receipt (demo).")
        inv = processed["03_arith_mismatch"]
        approvals.submit(db, inv, accountant, "Submitted for decision on total discrepancy.")
        approvals.reject(db, inv, approver, "Grand total overstated by Rs. 500; request a corrected invoice.")
        approvals.submit(db, processed["07_extra_items"], accountant, "Extra items need manager confirmation.")
        approvals.submit(db, processed["06_po_mismatch"], accountant, "Price variance vs PO - please review.")
        audit.record(db, action="demo.seed", company_id=company.id, meta={"historical_invoices": hist, "scenarios": len(SCENARIOS)})
        db.commit()
        summary = {k: {"status": str(v.status), "validation": str(v.validation_status), "duplicate": str(v.duplicate_status),
                       "po": str(v.po_match_status)} for k, v in processed.items()}
        return {"company": company.name, "historical": hist, "scenarios": summary}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()
    result = seed(args.reset)
    if result:
        print(f"Seeded demo company: {result['company']} ({result['historical']} historical invoices)")
        for k, v in result["scenarios"].items():
            print(f"  {k:20s} {v}")
        print(f"Demo users (password: {DEMO_PASSWORD}):")
        for email, name, role in DEMO_USERS:
            print(f"  {role:10s} {email}")
