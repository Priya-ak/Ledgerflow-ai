from __future__ import annotations

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class Supplier(IdMixin, TimestampMixin, Base):
    __tablename__ = "suppliers"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_supplier_company_code"),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(15), index=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    address: Mapped[str | None] = mapped_column(Text)
    contact_person: Mapped[str | None] = mapped_column(String(200))
    payment_terms_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
