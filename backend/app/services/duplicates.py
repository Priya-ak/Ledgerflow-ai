"""Deterministic duplicate invoice detection.

Signals (scored, explained):
  * same document checksum (identical file uploaded again)       -> duplicate
  * same supplier + same normalised invoice number                -> duplicate
  * same supplier + same amount + same date, different number     -> possible duplicate
  * same supplier + same amount within N days                     -> possible duplicate
Duplicates are stored and flagged - never silently discarded.
"""
from __future__ import annotations

import re
from datetime import timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Document, DuplicateMatch, Invoice
from app.models.enums import DuplicateStatus, InvoiceStatus
from app.services.gst import normalize_gstin


def normalize_invoice_number(num: str | None) -> str | None:
    if not num:
        return None
    n = re.sub(r"[^0-9A-Za-z]", "", num).upper()
    return n.lstrip("0") or n or None


def detect_duplicates(db: Session, inv: Invoice, window_days: int = 90) -> list[DuplicateMatch]:
    # Remove previous unresolved matches; resolved decisions are preserved.
    for old in db.scalars(select(DuplicateMatch).where(DuplicateMatch.invoice_id == inv.id, DuplicateMatch.resolution.is_(None))):
        db.delete(old)
    resolved_ids = set(db.scalars(select(DuplicateMatch.matched_invoice_id).where(
        DuplicateMatch.invoice_id == inv.id, DuplicateMatch.resolution == "not_duplicate")))

    supplier_clauses = []
    if inv.supplier_id:
        supplier_clauses.append(Invoice.supplier_id == inv.supplier_id)
    g = normalize_gstin(inv.supplier_gstin_raw)
    if g:
        supplier_clauses.append(Invoice.supplier_gstin_raw == g)
    candidates: list[Invoice] = []
    if supplier_clauses:
        candidates = list(db.scalars(select(Invoice).where(
            Invoice.company_id == inv.company_id, Invoice.id != inv.id,
            Invoice.status != InvoiceStatus.ARCHIVED, or_(*supplier_clauses)).limit(500)))

    checksums = {d.sha256 for d in inv.documents}
    same_doc_ids: set[str] = set()
    if checksums:
        same_doc_ids = set(db.scalars(select(Document.invoice_id).where(
            Document.company_id == inv.company_id, Document.sha256.in_(checksums),
            Document.invoice_id.is_not(None), Document.invoice_id != inv.id)))
        missing = same_doc_ids - {c.id for c in candidates}
        if missing:
            candidates += list(db.scalars(select(Invoice).where(Invoice.id.in_(missing), Invoice.company_id == inv.company_id)))

    matches: list[DuplicateMatch] = []
    for other in candidates:
        if other.id in resolved_ids:
            continue
        reasons, score = [], 0
        if other.id in same_doc_ids:
            reasons.append("Identical document file (same SHA-256 checksum).")
            score += 100
        if inv.invoice_number_normalized and inv.invoice_number_normalized == other.invoice_number_normalized:
            reasons.append(f"Same supplier and invoice number ({other.invoice_number}).")
            score += 80
        same_amount = inv.grand_total is not None and inv.grand_total == other.grand_total
        if same_amount:
            reasons.append(f"Same grand total ({other.grand_total}).")
            score += 20
        if inv.invoice_date and other.invoice_date:
            if inv.invoice_date == other.invoice_date:
                reasons.append("Same invoice date.")
                score += 15
            elif same_amount and abs((inv.invoice_date - other.invoice_date).days) <= window_days:
                reasons.append(f"Within {window_days} days of each other.")
                score += 5
        if score >= 80:
            mtype = "same_document" if other.id in same_doc_ids else "exact"
        elif same_amount and score >= 35:
            mtype = "probable"
        else:
            continue
        m = DuplicateMatch(company_id=inv.company_id, invoice_id=inv.id, matched_invoice_id=other.id,
                           match_type=mtype, score=min(score, 100), reasons=reasons)
        db.add(m)
        matches.append(m)

    has_unresolved_confirmed = db.scalar(select(DuplicateMatch.id).where(
        DuplicateMatch.invoice_id == inv.id, DuplicateMatch.resolution == "confirmed_duplicate").limit(1))
    if any(m.match_type in ("exact", "same_document") for m in matches) or has_unresolved_confirmed:
        inv.duplicate_status = DuplicateStatus.DUPLICATE
    elif matches:
        inv.duplicate_status = DuplicateStatus.POSSIBLE
    elif resolved_ids:
        inv.duplicate_status = DuplicateStatus.RESOLVED_NOT_DUPLICATE
    else:
        inv.duplicate_status = DuplicateStatus.NONE
    return matches
