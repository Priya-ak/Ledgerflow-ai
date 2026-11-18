from __future__ import annotations

from decimal import Decimal

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Money
from app.models.base import IdMixin, TimestampMixin


class Company(IdMixin, TimestampMixin, Base):
    __tablename__ = "companies"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    gstin: Mapped[str | None] = mapped_column(String(15), index=True)
    address: Mapped[str | None] = mapped_column(Text)
    state_code: Mapped[str | None] = mapped_column(String(2))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    settings: Mapped["CompanySettings"] = relationship(back_populates="company", uselist=False, cascade="all, delete-orphan")


class CompanySettings(IdMixin, TimestampMixin, Base):
    """Per-company processing and validation configuration."""

    __tablename__ = "company_settings"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    amount_tolerance: Mapped[Decimal] = mapped_column(Money(), default=Decimal("1.00"), nullable=False)
    po_price_tolerance_pct: Mapped[Decimal] = mapped_column(Money(), default=Decimal("2.00"), nullable=False)
    po_qty_tolerance_pct: Mapped[Decimal] = mapped_column(Money(), default=Decimal("0.00"), nullable=False)
    duplicate_window_days: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    require_mfa: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notify_approvers: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    company: Mapped[Company] = relationship(back_populates="settings")
