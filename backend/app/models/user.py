from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import IdMixin, TimestampMixin, UTCDateTime
from app.models.organization import Company


class User(IdMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (UniqueConstraint("email", name="uq_users_email"),)

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    # Incremented on logout/password change -> invalidates all issued tokens.
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime())

    # Two-factor authentication (TOTP). Secrets are Fernet-encrypted at rest.
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    mfa_secret_enc: Mapped[str | None] = mapped_column(String(255))
    mfa_pending_secret_enc: Mapped[str | None] = mapped_column(String(255))
    mfa_enabled_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    mfa_last_step: Mapped[int | None] = mapped_column(Integer)  # replay protection

    company: Mapped[Company] = relationship()


class PasswordResetToken(IdMixin, TimestampMixin, Base):
    __tablename__ = "password_reset_tokens"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # HMAC-SHA256 hex
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())


class MfaRecoveryCode(IdMixin, TimestampMixin, Base):
    """One-time recovery codes; only an HMAC hash is stored."""

    __tablename__ = "mfa_recovery_codes"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
