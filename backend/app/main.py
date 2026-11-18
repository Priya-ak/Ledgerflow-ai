"""LedgerFlow AI - FastAPI application entrypoint."""
from __future__ import annotations

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, analytics, approvals, audit_logs, auth, documents, invoices, purchase_orders, reports, suppliers, system
from app.core.config import settings
from app.core.errors import install_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging

configure_logging()

app = FastAPI(
    title="LedgerFlow AI API",
    version="1.0.0",
    description="Invoice processing: OCR, structured extraction, deterministic validation, "
                "duplicate detection, PO matching and human approval workflows.",
    docs_url="/api/docs", redoc_url="/api/redoc", openapi_url="/api/openapi.json",
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.FRONTEND_URL.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Content-Disposition"],
)
install_error_handlers(app)

v1 = APIRouter(prefix="/api/v1")
for r in (auth, admin, suppliers, purchase_orders, documents, invoices, approvals, analytics, reports, audit_logs, system):
    v1.include_router(r.router)
app.include_router(v1)


@app.get("/", include_in_schema=False)
def root():
    return {"name": settings.APP_NAME, "docs": "/api/docs"}
