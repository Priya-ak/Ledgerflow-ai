from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, Query, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.api.pagination import paginate
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, get_owned, require
from app.core.errors import AppError, BusinessRuleError
from app.models import Document, Invoice
from app.models.base import new_id
from app.models.enums import InvoiceStatus
from app.schemas.common import Page
from app.schemas.entities import DocumentOut
from app.services import audit
from app.services.file_types import CONTENT_TYPES, EXTENSIONS, sniff
from app.services.malware import ScanResult, ScannerUnavailable, antivirus_scan, pdf_policy_scan
from app.services.storage import build_key, get_storage

router = APIRouter(prefix="/documents", tags=["documents"])
CHUNK = 64 * 1024


class UploadRejected(AppError):
    status_code, code = 415, "unsupported_file"


class MalwareDetected(AppError):
    status_code, code = 422, "malware_detected"


class ScannerDown(AppError):
    status_code, code = 503, "scanner_unavailable"


def _safe_display_name(name: str | None) -> str:
    base = os.path.basename((name or "document").replace("\\", "/"))
    cleaned = "".join(c for c in base if c.isalnum() or c in "._- ")[:120].strip()
    return cleaned or "document"


def _deep_validate(path: Path, kind: str) -> int | None:
    """Open the file with the real parser; reject anything that does not parse."""
    if kind == "pdf":
        import fitz
        try:
            with fitz.open(path) as doc:
                if doc.needs_pass:
                    raise UploadRejected("Password-protected PDFs are not supported.")
                if doc.page_count < 1:
                    raise UploadRejected("PDF has no pages.")
                return doc.page_count
        except UploadRejected:
            raise
        except Exception:
            raise UploadRejected("File is not a valid PDF.")
    from PIL import Image
    try:
        with Image.open(path) as img:
            img.verify()
        with Image.open(path) as img:
            if img.width * img.height > 40_000_000:
                raise UploadRejected("Image dimensions are too large.")
    except UploadRejected:
        raise
    except Exception:
        raise UploadRejected("File is not a valid image.")
    return 1


def _reject_malware(db: Session, current: CurrentUser, request: Request, filename: str | None, sha256: str,
                    size: int, scan: ScanResult) -> None:
    audit.record(db, action="document.rejected_malware", company_id=current.company_id, actor=current.user,
                 entity_type="document", request=request,
                 meta={"filename": _safe_display_name(filename), "sha256": sha256, "size": size,
                       "engine": scan.engine, "signature": scan.signature, "detail": scan.detail})
    db.commit()
    msg = ("This file was blocked by the virus scanner." if scan.engine == "clamav"
           else f"This PDF contains active content that invoices never need ({scan.detail}) and was blocked.")
    raise MalwareDetected(msg, details={"engine": scan.engine, "signature": scan.signature})


@router.post("/upload", response_model=DocumentOut, status_code=201)
async def upload(request: Request, file: UploadFile = File(...),
                 current: CurrentUser = Depends(require("documents:upload")), db: Session = Depends(get_db)):
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    ext = Path(file.filename or "").suffix.lower()
    sha, size = hashlib.sha256(), 0
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp_path = Path(tmp.name)
        try:
            head = b""
            while chunk := await file.read(CHUNK):  # streamed: never loads the whole file in RAM
                size += len(chunk)
                if size > max_bytes:
                    raise AppError(f"File exceeds the {settings.MAX_UPLOAD_MB} MB limit.", code="file_too_large", status_code=413)
                if len(head) < 16:
                    head += chunk[:16]
                sha.update(chunk)
                tmp.write(chunk)
        except Exception:
            tmp.close()
            tmp_path.unlink(missing_ok=True)
            raise
    try:
        if size == 0:
            raise UploadRejected("File is empty.")
        try:
            av = antivirus_scan(tmp_path)  # raw bytes first, before any parser runs
        except ScannerUnavailable:
            raise ScannerDown("The virus scanner is unavailable, so uploads are paused. Please try again shortly.")
        if not av.clean:
            _reject_malware(db, current, request, file.filename, sha.hexdigest(), size, av)
        kind = sniff(head)
        if kind is None:
            raise UploadRejected("Only PDF, JPG and PNG files are supported.")
        if ext not in EXTENSIONS[kind]:
            raise UploadRejected(f"File extension '{ext or 'none'}' does not match its content ({kind}).")
        pages = _deep_validate(tmp_path, kind)
        policy = pdf_policy_scan(tmp_path) if kind == "pdf" else ScanResult(True, "")
        if not policy.clean:
            _reject_malware(db, current, request, file.filename, sha.hexdigest(), size, policy)
        engines = "+".join(e for e in (av.engine if av.engine != "none" else "", policy.engine) if e) or "none"
        doc_id = new_id()
        key = build_key(current.company_id, doc_id, "jpg" if kind == "jpeg" else kind)
        storage = get_storage()
        storage.save(key, tmp_path, CONTENT_TYPES[kind])
    finally:
        tmp_path.unlink(missing_ok=True)
    doc = Document(id=doc_id, company_id=current.company_id, uploaded_by_id=current.id,
                   original_filename=_safe_display_name(file.filename), storage_provider=storage.name,
                   storage_key=key, content_type=CONTENT_TYPES[kind], size_bytes=size, sha256=sha.hexdigest(),
                   page_count=pages, scan_engine=engines, scan_result="clean" if engines != "none" else "not_scanned")
    db.add(doc)
    audit.record(db, action="document.upload", company_id=current.company_id, actor=current.user, entity_type="document",
                 entity_id=doc.id, meta={"filename": doc.original_filename, "size": size, "type": kind}, request=request)
    db.commit()
    return doc


@router.get("", response_model=Page[DocumentOut])
def list_documents(status: str | None = None, unprocessed: bool = False, page: int = Query(1, ge=1),
                   page_size: int = Query(20, ge=1, le=100), current: CurrentUser = Depends(require("documents:read")),
                   db: Session = Depends(get_db)):
    stmt = select(Document).where(Document.company_id == current.company_id)
    if status:
        stmt = stmt.where(Document.status == status)
    if unprocessed:
        stmt = stmt.where(Document.invoice_id.is_(None))
    return paginate(db, stmt.order_by(Document.created_at.desc()), page, page_size, DocumentOut)


@router.get("/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: str, current: CurrentUser = Depends(require("documents:read")), db: Session = Depends(get_db)):
    return get_owned(db, Document, doc_id, current.company_id)


@router.get("/{doc_id}/download")
def download(doc_id: str, inline: bool = True, current: CurrentUser = Depends(require("documents:read")),
             db: Session = Depends(get_db)):
    """Authorised file access. Storage is never exposed directly to clients."""
    doc = get_owned(db, Document, doc_id, current.company_id)
    storage = get_storage()
    cm = storage.local_path(doc.storage_key)
    path = cm.__enter__()
    disposition = "inline" if inline else "attachment"
    return FileResponse(path, media_type=doc.content_type, filename=doc.original_filename,
                        content_disposition_type=disposition,
                        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
                        background=BackgroundTask(cm.__exit__, None, None, None))


@router.delete("/{doc_id}", response_model=DocumentOut)
def delete_document(doc_id: str, request: Request, current: CurrentUser = Depends(require("documents:delete")),
                    db: Session = Depends(get_db)):
    doc = get_owned(db, Document, doc_id, current.company_id)
    if doc.invoice_id:
        inv = db.get(Invoice, doc.invoice_id)
        if inv and inv.status in (InvoiceStatus.PENDING_APPROVAL, InvoiceStatus.APPROVED):
            raise BusinessRuleError("Documents of pending or approved invoices are retained for audit and cannot be deleted.")
    out = DocumentOut.model_validate(doc)
    get_storage().delete(doc.storage_key)
    audit.record(db, action="document.delete", company_id=current.company_id, actor=current.user, entity_type="document",
                 entity_id=doc.id, meta={"filename": doc.original_filename, "sha256": doc.sha256}, request=request)
    db.delete(doc)
    db.commit()
    return out


@router.get("/{doc_id}/preview")
def preview(doc_id: str, page: int = Query(1, ge=1), current: CurrentUser = Depends(require("documents:read")),
            db: Session = Depends(get_db)):
    """Compressed PNG preview of one page (works in every browser, low memory)."""
    import io

    from fastapi.responses import Response
    from PIL import Image

    doc = get_owned(db, Document, doc_id, current.company_id)
    with get_storage().local_path(doc.storage_key) as path:
        if doc.content_type == "application/pdf":
            import fitz
            with fitz.open(path) as pdf:
                if page > pdf.page_count:
                    raise BusinessRuleError(f"Document has {pdf.page_count} page(s).")
                pix = pdf.load_page(page - 1).get_pixmap(dpi=110)
                data = pix.tobytes("png")
                del pix
        else:
            if page != 1:
                raise BusinessRuleError("Images have a single page.")
            with Image.open(path) as img:
                img.thumbnail((1400, 2000))
                buf = io.BytesIO()
                img.convert("RGB").save(buf, "PNG", optimize=True)
                data = buf.getvalue()
    return Response(data, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})
