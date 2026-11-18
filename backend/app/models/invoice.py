from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, Money
from app.models.base import IdMixin, TimestampMixin, utcnow, UTCDateTime
from app.models.document import Document
from app.models.purchase_order import PurchaseOrder
from app.models.supplier import Supplier


class Invoice(IdMixin, TimestampMixin, Base):
    __tablename__ = "invoices"
    __table_args__ = (
        # Fast duplicate lookups; uniqueness is a business rule, not a constraint,
        # because duplicates must be stored and flagged rather than rejected.
        Index("ix_invoice_dup_lookup", "company_id", "supplier_id", "invoice_number_normalized"),
        Index("ix_invoice_company_status", "company_id", "status"),
        Index("ix_invoice_company_date", "company_id", "invoice_date"),
    )

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    supplier_id: Mapped[str | None] = mapped_column(ForeignKey("suppliers.id"), index=True)
    purchase_order_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_orders.id"), index=True)

    invoice_number: Mapped[str | None] = mapped_column(String(60))
    invoice_number_normalized: Mapped[str | None] = mapped_column(String(60))
    invoice_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date)
    po_number_ref: Mapped[str | None] = mapped_column(String(60))  # PO number as printed on the invoice
    currency: Mapped[str] = mapped_column(String(3), default="INR", nullable=False)

    # Supplier details as printed on the document (may differ from master data)
    supplier_name_raw: Mapped[str | None] = mapped_column(String(200))
    supplier_gstin_raw: Mapped[str | None] = mapped_column(String(15))
    supplier_address_raw: Mapped[str | None] = mapped_column(Text)
    buyer_name: Mapped[str | None] = mapped_column(String(200))
    buyer_gstin: Mapped[str | None] = mapped_column(String(15))
    buyer_address: Mapped[str | None] = mapped_column(Text)

    subtotal: Mapped[Decimal | None] = mapped_column(Money())
    discount: Mapped[Decimal | None] = mapped_column(Money())
    taxable_amount: Mapped[Decimal | None] = mapped_column(Money())
    cgst: Mapped[Decimal | None] = mapped_column(Money())
    sgst: Mapped[Decimal | None] = mapped_column(Money())
    igst: Mapped[Decimal | None] = mapped_column(Money())
    other_charges: Mapped[Decimal | None] = mapped_column(Money())
    total_tax: Mapped[Decimal | None] = mapped_column(Money())
    grand_total: Mapped[Decimal | None] = mapped_column(Money())

    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)
    payment_status: Mapped[str] = mapped_column(String(20), default="unpaid", nullable=False)
    validation_status: Mapped[str] = mapped_column(String(20), default="not_run", nullable=False)
    duplicate_status: Mapped[str] = mapped_column(String(30), default="none", nullable=False)
    po_match_status: Mapped[str] = mapped_column(String(30), default="not_run", nullable=False)
    has_critical_errors: Mapped[bool] = mapped_column(default=False, nullable=False)

    extracted_data: Mapped[dict | None] = mapped_column(JSON)  # raw structured extraction (immutable snapshot)
    extraction_method: Mapped[str | None] = mapped_column(String(30))
    needs_review_fields: Mapped[list | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)

    created_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    submitted_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    supplier: Mapped[Supplier | None] = relationship()
    purchase_order: Mapped[PurchaseOrder | None] = relationship()
    items: Mapped[list["InvoiceItem"]] = relationship(
        back_populates="invoice", cascade="all, delete-orphan", order_by="InvoiceItem.line_no"
    )
    documents: Mapped[list[Document]] = relationship(foreign_keys=[Document.invoice_id])


class InvoiceItem(IdMixin, Base):
    __tablename__ = "invoice_items"

    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False)
    line_no: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str | None] = mapped_column(String(500))
    hsn_sac: Mapped[str | None] = mapped_column(String(10))
    quantity: Mapped[Decimal | None] = mapped_column(Money(3))
    unit: Mapped[str | None] = mapped_column(String(20))
    unit_price: Mapped[Decimal | None] = mapped_column(Money())
    discount: Mapped[Decimal | None] = mapped_column(Money())
    taxable_value: Mapped[Decimal | None] = mapped_column(Money())
    tax_rate: Mapped[Decimal | None] = mapped_column(Money())
    tax_amount: Mapped[Decimal | None] = mapped_column(Money())
    line_total: Mapped[Decimal | None] = mapped_column(Money())

    invoice: Mapped[Invoice] = relationship(back_populates="items")


class ValidationResult(IdMixin, Base):
    """History of validation runs; the latest row is the current report."""

    __tablename__ = "validation_results"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    report: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class DuplicateMatch(IdMixin, Base):
    __tablename__ = "duplicate_matches"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False)
    matched_invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False)
    match_type: Mapped[str] = mapped_column(String(30), nullable=False)  # exact | probable | same_document
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    reasons: Mapped[list] = mapped_column(JSON, nullable=False)
    resolution: Mapped[str | None] = mapped_column(String(30))  # not_duplicate | confirmed_duplicate
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class PoMatchResult(IdMixin, Base):
    __tablename__ = "po_match_results"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False)
    purchase_order_id: Mapped[str | None] = mapped_column(ForeignKey("purchase_orders.id"))
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    report: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
