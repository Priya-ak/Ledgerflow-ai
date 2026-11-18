from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, utcnow, UTCDateTime


class ApprovalPolicy(IdMixin, TimestampMixin, Base):
    """Company approval configuration.

    levels: ordered list of {"level": 1, "name": "Manager", "role": "approver", "min_amount": "0"}.
    A level applies when invoice grand_total >= min_amount. Default: one level.
    """

    __tablename__ = "approval_policies"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    levels: Mapped[list] = mapped_column(JSON, nullable=False)
    allow_self_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    allow_critical_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class ApprovalRequest(IdMixin, TimestampMixin, Base):
    __tablename__ = "approval_requests"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id", ondelete="CASCADE"), index=True, nullable=False)
    submitted_by_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False, index=True)
    current_level: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    required_levels: Mapped[list] = mapped_column(JSON, nullable=False)  # snapshot of applicable levels
    submission_note: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    steps: Mapped[list["ApprovalStep"]] = relationship(back_populates="request", cascade="all, delete-orphan", order_by="ApprovalStep.created_at")


class ApprovalStep(IdMixin, Base):
    """Immutable record of one approver decision."""

    __tablename__ = "approval_steps"

    request_id: Mapped[str] = mapped_column(ForeignKey("approval_requests.id", ondelete="CASCADE"), index=True, nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    approver_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # approved | rejected
    comment: Mapped[str | None] = mapped_column(Text)
    override_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)

    request: Mapped[ApprovalRequest] = relationship(back_populates="steps")
