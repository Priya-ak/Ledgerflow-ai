"""Synchronous document-processing pipeline.

upload -> stored -> text (PyMuPDF / Tesseract) -> rule extraction -> optional AI refine
-> structured, schema-validated JSON -> invoice -> duplicates/PO/validation -> human review.

Runs one document at a time to stay within ~4 GB RAM. The function is
self-contained so it can later be moved to a background worker unchanged.
"""
from __future__ import annotations

import logging
import time

from sqlalchemy.orm import Session

from app.core.errors import BusinessRuleError
from app.ml.providers import refine_with_fallback
from app.models import Document, Invoice, ProcessingRecord
from app.models.enums import DocumentStatus, InvoiceStatus
from app.schemas.extraction import ExtractedInvoice
from app.services.extraction import extract_fields
from app.services.invoices import apply_extraction, run_checks
from app.services.storage import get_storage
from app.services.text_extraction import OcrUnavailable, extract_text

log = logging.getLogger("ledgerflow.pipeline")

KIND_BY_TYPE = {"application/pdf": "pdf", "image/png": "png", "image/jpeg": "jpeg"}


def process_document(db: Session, doc: Document, user_id: str | None) -> tuple[Invoice, ProcessingRecord]:
    if doc.invoice_id:
        raise BusinessRuleError("This document has already been processed into an invoice.")
    start = time.perf_counter()
    doc.status = DocumentStatus.PROCESSING
    inv = Invoice(company_id=doc.company_id, status=InvoiceStatus.PROCESSING, created_by_id=user_id, is_demo=doc.is_demo)
    db.add(inv)
    db.flush()
    doc.invoice_id = inv.id
    rec = ProcessingRecord(company_id=doc.company_id, document_id=doc.id, invoice_id=inv.id, status="failed")
    db.add(rec)
    try:
        with get_storage().local_path(doc.storage_key) as path:
            text_res = extract_text(path, KIND_BY_TYPE[doc.content_type])
        doc.page_count = text_res.page_count
        rec.text_method, rec.ocr_confidence = text_res.method, text_res.ocr_confidence
        rec.raw_text = text_res.text[:50_000]
        if not text_res.text.strip():
            raise BusinessRuleError("No readable text found in the document.", details=text_res.warnings)
        extracted = extract_fields(text_res.text, text_method=text_res.method,
                                   ocr_confidence=text_res.ocr_confidence, extra_warnings=text_res.warnings)
        extracted = refine_with_fallback(text_res.text, extracted)
        extracted = ExtractedInvoice.model_validate(extracted.model_dump())  # final schema gate
        inv.status = InvoiceStatus.EXTRACTED
        apply_extraction(db, inv, extracted)
        run_checks(db, inv)
        doc.status = DocumentStatus.PROCESSED
        rec.status = "succeeded"
        rec.extraction_method = extracted.extraction_metadata.method
        rec.warnings = extracted.extraction_metadata.warnings
    except (OcrUnavailable, BusinessRuleError, ValueError) as e:
        log.warning("processing_failed doc=%s reason=%s", doc.id, e)
        doc.status = DocumentStatus.FAILED
        doc.error_message = str(e)[:500]
        inv.status = InvoiceStatus.FAILED_PROCESSING
        inv.needs_review_fields = ["all"]
        rec.error_message = str(e)[:500]
    finally:
        rec.duration_ms = int((time.perf_counter() - start) * 1000)
    return inv, rec
