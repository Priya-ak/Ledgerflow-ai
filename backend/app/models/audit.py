from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, event
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import IdMixin, utcnow, UTCDateTime


class AuditLog(IdMixin, Base):
    """Append-only audit trail. Updates/deletes are blocked at the ORM layer."""

    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_company_created", "company_id", "created_at"),)

    company_id: Mapped[str | None] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"))
    actor_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    actor_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(36), index=True)
    meta: Mapped[dict | None] = mapped_column("metadata", JSON)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    request_id: Mapped[str | None] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, nullable=False)


class AuditImmutableError(RuntimeError):
    pass


@event.listens_for(AuditLog, "before_update")
def _block_update(*_):
    raise AuditImmutableError("Audit log entries are immutable")


@event.listens_for(AuditLog, "before_delete")
def _block_delete(*_):
    raise AuditImmutableError("Audit log entries cannot be deleted")
