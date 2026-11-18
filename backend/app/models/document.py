from __future__ import annotations

from sqlalchemy import JSON, BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin


class Document(IdMixin, TimestampMixin, Base):
    __tablename__ = "documents"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"), index=True)
    uploaded_by_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)  # display only, never used for paths
    storage_provider: Mapped[str] = mapped_column(String(20), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="uploaded", nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(default=False, nullable=False)
    # Malware / active-content scan outcome recorded at upload.
    scan_engine: Mapped[str | None] = mapped_column(String(60))
    scan_result: Mapped[str | None] = mapped_column(String(20))  # clean | skipped


class ProcessingRecord(IdMixin, TimestampMixin, Base):
    """One row per pipeline run on a document (processing history)."""

    __tablename__ = "processing_records"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[str | None] = mapped_column(ForeignKey("invoices.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # succeeded | failed
    text_method: Mapped[str | None] = mapped_column(String(20))  # pdf_text | ocr | mixed
    extraction_method: Mapped[str | None] = mapped_column(String(30))  # rules | rules+ollama | rules+gemini
    ocr_confidence: Mapped[float | None] = mapped_column()
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    warnings: Mapped[list | None] = mapped_column(JSON)
    error_message: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str | None] = mapped_column(Text)
