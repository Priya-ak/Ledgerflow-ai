from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IdMixin, UTCDateTime, utcnow


class EmailLog(IdMixin, Base):
    """Delivery record for every outbound email. Bodies (which may contain links/tokens) are never stored."""

    __tablename__ = "email_logs"
    __table_args__ = (Index("ix_email_company_created", "company_id", "created_at"),)

    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    to_email: Mapped[str] = mapped_column(String(255), nullable=False)
    template: Mapped[str] = mapped_column(String(60), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # sent | failed | skipped
    provider_message_id: Mapped[str | None] = mapped_column(String(255))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)
