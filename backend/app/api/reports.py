from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, require
from app.core.errors import NotFound
from app.services import audit
from app.services.reports import REPORTS, to_xlsx

router = APIRouter(prefix="/reports", tags=["reports"])
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _filters(status: str | None, supplier_id: str | None, date_from: date | None, date_to: date | None) -> dict:
    return {"status": status, "supplier_id": supplier_id, "date_from": date_from, "date_to": date_to}


def _json(ds: dict) -> dict:
    conv = lambda v: str(v) if isinstance(v, Decimal) else (v.isoformat() if isinstance(v, (date, datetime)) else v)  # noqa: E731
    return {"title": ds["title"], "columns": ds["columns"], "rows": [[conv(v) for v in r] for r in ds["rows"][:500]],
            "total_rows": len(ds["rows"])}


def _export(db: Session, current: CurrentUser, request: Request, names: list[str], f: dict) -> Response:
    data = to_xlsx([REPORTS[n](db, current.company_id, f) for n in names], current.user.company.name)
    audit.record(db, action="report.export", company_id=current.company_id, actor=current.user, request=request,
                 meta={"reports": names, "filters": {k: str(v) for k, v in f.items() if v}})
    db.commit()
    fname = f"ledgerflow-{'-'.join(names) if len(names) < 3 else 'reports'}-{date.today().isoformat()}.xlsx"
    return Response(data, media_type=XLSX, headers={"Content-Disposition": f'attachment; filename="{fname}"'})


@router.get("/invoices/export")
def export_invoices(request: Request, status: str | None = None, supplier_id: str | None = None,
                    date_from: date | None = None, date_to: date | None = None,
                    include: str = Query("invoices,invoice-details", description="Comma-separated report sheets"),
                    current: CurrentUser = Depends(require("reports:export")), db: Session = Depends(get_db)):
    names = [n for n in include.split(",") if n in REPORTS] or ["invoices"]
    return _export(db, current, request, names, _filters(status, supplier_id, date_from, date_to))


@router.get("/{kind}/export")
def export_kind(kind: str, request: Request, status: str | None = None, supplier_id: str | None = None,
                date_from: date | None = None, date_to: date | None = None,
                current: CurrentUser = Depends(require("reports:export")), db: Session = Depends(get_db)):
    if kind not in REPORTS:
        raise NotFound("Unknown report.")
    return _export(db, current, request, [kind], _filters(status, supplier_id, date_from, date_to))


@router.get("/{kind}")
def report(kind: str, status: str | None = None, supplier_id: str | None = None, date_from: date | None = None,
           date_to: date | None = None, current: CurrentUser = Depends(require("reports:export")),
           db: Session = Depends(get_db)):
    """JSON preview (first 500 rows) of a report."""
    if kind not in REPORTS:
        raise NotFound("Unknown report.")
    return _json(REPORTS[kind](db, current.company_id, _filters(status, supplier_id, date_from, date_to)))
