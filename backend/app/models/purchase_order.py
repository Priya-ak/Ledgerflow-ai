from __future__ import annotations

from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Money
from app.models.base import IdMixin, TimestampMixin
from app.models.supplier import Supplier


class PurchaseOrder(IdMixin, TimestampMixin, Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (UniqueConstraint("company_id", "po_number", name="uq_po_company_number"),)

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True, nullable=False)
    po_number: Mapped[str] = mapped_column(String(60), nullable=False)
    po_date: Mapped[date] = mapped_column(Date, nullable=False)
    expected_delivery_date: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)
    subtotal: Mapped[Decimal] = mapped_column(Money(), default=Decimal("0"), nullable=False)
    tax_total: Mapped[Decimal] = mapped_column(Money(), default=Decimal("0"), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Money(), default=Decimal("0"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="open", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))

    supplier: Mapped[Supplier] = relationship()
    items: Mapped[list["PurchaseOrderItem"]] = relationship(
        back_populates="purchase_order", cascade="all, delete-orphan", order_by="PurchaseOrderItem.line_no"
    )


class PurchaseOrderItem(IdMixin, Base):
    __tablename__ = "purchase_order_items"

    purchase_order_id: Mapped[str] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), index=True, nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    hsn_sac: Mapped[str | None] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(Money(3), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(20))
    unit_price: Mapped[Decimal] = mapped_column(Money(), nullable=False)
    tax_rate: Mapped[Decimal] = mapped_column(Money(), default=Decimal("0"), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Money(), nullable=False)

    purchase_order: Mapped[PurchaseOrder] = relationship(back_populates="items")
