from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.ratelimit import client_ip
from app.ml.providers import ai_status
from app.services.malware import clamd_ping, clamd_version
from app.services.text_extraction import ocr_available

router = APIRouter(tags=["system"])


@router.get("/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}


@router.get("/system/status")
def system_status(request: Request, _: CurrentUser = Depends(get_current_user)):
    return {
        "client": {"ip": client_ip(request), "forwarded_hops_seen": len([p for p in request.headers.get("x-forwarded-for", "").split(",") if p.strip()]),
                   "trusted_proxy_hops": settings.TRUSTED_PROXY_HOPS},
        "app": settings.APP_NAME, "environment": settings.APP_ENV, "demo_mode": settings.DEMO_MODE,
        "database": "sqlite" if settings.is_sqlite else "postgresql",
        "storage": settings.STORAGE_PROVIDER,
        "ocr": {"engine": settings.OCR_ENGINE, "available": ocr_available()},
        "ai": ai_status(),
        "malware_scanning": {
            "pdf_active_content_policy": True,
            "engine": settings.MALWARE_SCANNER,
            "available": clamd_ping() if settings.MALWARE_SCANNER == "clamav" else None,
            "version": clamd_version() if settings.MALWARE_SCANNER == "clamav" else None,
            "fail_closed": settings.MALWARE_SCAN_FAIL_CLOSED,
        },
        "email": {"provider": settings.EMAIL_PROVIDER, "from": settings.EMAIL_FROM},
        "limits": {"max_upload_mb": settings.MAX_UPLOAD_MB, "max_pdf_pages": settings.MAX_PDF_PAGES},
    }
