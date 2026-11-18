"""Symmetric encryption for secrets stored at rest (e.g. TOTP seeds).

Uses Fernet (AES-128-CBC + HMAC-SHA256). The key comes from ENCRYPTION_KEY; in
development only, a key is derived from SECRET_KEY so local setups work.
"""
from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings


class DecryptionError(RuntimeError):
    pass


@lru_cache
def _fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if not key:
        # Development fallback: deterministic derivation from SECRET_KEY.
        key = base64.urlsafe_b64encode(hashlib.sha256(("lf-enc:" + settings.SECRET_KEY).encode()).digest()).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as e:
        raise DecryptionError("Stored secret could not be decrypted (wrong ENCRYPTION_KEY?).") from e


def new_key() -> str:
    return Fernet.generate_key().decode()
