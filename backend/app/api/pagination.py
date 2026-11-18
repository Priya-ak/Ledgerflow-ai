from __future__ import annotations

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.schemas.common import Page


def paginate(db: Session, stmt: Select, page: int, page_size: int, schema) -> Page:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    rows = db.scalars(stmt.limit(page_size).offset((page - 1) * page_size)).unique().all()
    return Page(items=[schema.model_validate(r) for r in rows], total=total, page=page, page_size=page_size)
