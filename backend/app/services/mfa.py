"""TOTP two-factor authentication (RFC 6238) with one-time recovery codes."""
from __future__ import annotations

import hashlib
import hmac
import io
import secrets
import time
from datetime import datetime, timezone

import pyotp
import segno
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import decrypt, encrypt
from app.models import MfaRecoveryCode, User

RECOVERY_CODE_COUNT = 10
STEP = 30


def _hash_code(code: str) -> str:
    norm = code.replace("-", "").replace(" ", "").lower()
    return hmac.new(settings.SECRET_KEY.encode(), f"mfa-recovery:{norm}".encode(), hashlib.sha256).hexdigest()


def begin_setup(user: User) -> dict:
    """Create a pending secret; it becomes active only after a valid code is confirmed."""
    secret = pyotp.random_base32(32)
    user.mfa_pending_secret_enc = encrypt(secret)
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=settings.MFA_ISSUER)
    buf = io.BytesIO()
    segno.make(uri, error="m").save(buf, kind="svg", scale=5, border=2, dark="#0f172a", light="#ffffff")
    return {"secret": secret, "otpauth_uri": uri, "qr_svg": buf.getvalue().decode()}


def _verify(secret: str, code: str, last_step: int | None) -> int | None:
    """Return the matched time step, or None. Accepts ±1 step drift; rejects reuse."""
    code = code.strip().replace(" ", "")
    if not (code.isdigit() and len(code) == 6):
        return None
    totp = pyotp.TOTP(secret)
    now_step = int(time.time()) // STEP
    for step in (now_step, now_step - 1, now_step + 1):
        if hmac.compare_digest(totp.at(step * STEP), code):
            if last_step is not None and step <= last_step:
                return None  # replayed code
            return step
    return None


def confirm_setup(db: Session, user: User, code: str) -> list[str] | None:
    if not user.mfa_pending_secret_enc:
        return None
    secret = decrypt(user.mfa_pending_secret_enc)
    step = _verify(secret, code, None)
    if step is None:
        return None
    user.mfa_secret_enc, user.mfa_pending_secret_enc = user.mfa_pending_secret_enc, None
    user.mfa_enabled, user.mfa_enabled_at, user.mfa_last_step = True, datetime.now(timezone.utc), step
    return regenerate_recovery_codes(db, user)


def regenerate_recovery_codes(db: Session, user: User) -> list[str]:
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
    codes = [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(RECOVERY_CODE_COUNT)]
    for c in codes:
        db.add(MfaRecoveryCode(user_id=user.id, code_hash=_hash_code(c)))
    return codes


def verify_login(db: Session, user: User, code: str) -> str | None:
    """Return 'totp' or 'recovery_code' on success, None on failure."""
    if not user.mfa_enabled or not user.mfa_secret_enc:
        return None
    step = _verify(decrypt(user.mfa_secret_enc), code, user.mfa_last_step)
    if step is not None:
        user.mfa_last_step = step
        return "totp"
    rc = db.scalar(select(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id,
                                                 MfaRecoveryCode.code_hash == _hash_code(code),
                                                 MfaRecoveryCode.used_at.is_(None)))
    if rc:
        rc.used_at = datetime.now(timezone.utc)
        return "recovery_code"
    return None


def remaining_recovery_codes(db: Session, user: User) -> int:
    return len(db.scalars(select(MfaRecoveryCode.id).where(MfaRecoveryCode.user_id == user.id,
                                                           MfaRecoveryCode.used_at.is_(None))).all())


def disable(db: Session, user: User) -> None:
    user.mfa_enabled, user.mfa_secret_enc, user.mfa_pending_secret_enc = False, None, None
    user.mfa_enabled_at, user.mfa_last_step = None, None
    db.execute(delete(MfaRecoveryCode).where(MfaRecoveryCode.user_id == user.id))
