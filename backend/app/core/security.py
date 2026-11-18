"""Password hashing, JWT session tokens, and reset-token hashing."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.core.config import settings

JWT_ALG = "HS256"


def hash_password(password: str) -> str:
    # bcrypt only uses the first 72 bytes; schemas cap length so this is explicit.
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], password_hash.encode())
    except ValueError:
        return False


SCOPE_FULL = "full"
SCOPE_MFA_ENROLL = "mfa_enroll"  # may only reach the MFA enrolment endpoints


def create_access_token(user_id: str, company_id: str, role: str, token_version: int, scope: str = SCOPE_FULL) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "cid": company_id,
        "role": role,
        "tv": token_version,
        "typ": "session",
        "scp": scope,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)).timestamp()),
        "iss": "ledgerflow",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=JWT_ALG)


def decode_access_token(token: str) -> dict:
    claims = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALG], issuer="ledgerflow",
                        options={"require": ["sub", "exp", "iat", "typ"]})
    if claims.get("typ") != "session":
        raise jwt.InvalidTokenError("Not a session token")
    return claims


def create_mfa_challenge_token(user_id: str, token_version: int) -> str:
    """Short-lived proof that the password step succeeded; useless as a session."""
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": user_id, "tv": token_version, "typ": "mfa_challenge", "iat": int(now.timestamp()),
                       "exp": int((now + timedelta(minutes=5)).timestamp()), "iss": "ledgerflow"},
                      settings.JWT_SECRET, algorithm=JWT_ALG)


def decode_mfa_challenge_token(token: str) -> dict:
    claims = jwt.decode(token, settings.JWT_SECRET, algorithms=[JWT_ALG], issuer="ledgerflow",
                        options={"require": ["sub", "exp", "typ"]})
    if claims.get("typ") != "mfa_challenge":
        raise jwt.InvalidTokenError("Not an MFA challenge token")
    return claims


def new_reset_token() -> tuple[str, str]:
    """Return (raw_token_for_user, hmac_hash_for_db). Only the hash is stored."""
    raw = secrets.token_urlsafe(32)
    return raw, hash_reset_token(raw)


def hash_reset_token(raw: str) -> str:
    return hmac.new(settings.SECRET_KEY.encode(), raw.encode(), hashlib.sha256).hexdigest()
