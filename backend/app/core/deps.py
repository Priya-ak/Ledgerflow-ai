"""FastAPI dependencies: authenticated user, permission checks, tenant-scoped lookups."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

import jwt
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.errors import Forbidden, NotFound, Unauthorized
from app.core.permissions import has_permission
from app.core.security import SCOPE_MFA_ENROLL, decode_access_token
from app.models import User

T = TypeVar("T")


MFA_ENROLL_ALLOWED = {"/api/v1/auth/me", "/api/v1/auth/logout", "/api/v1/auth/mfa", "/api/v1/auth/mfa/setup",
                      "/api/v1/auth/mfa/enable"}


@dataclass
class CurrentUser:
    user: User
    scope: str = "full"

    @property
    def id(self) -> str:
        return self.user.id

    @property
    def company_id(self) -> str:
        # Tenant is ALWAYS derived from the authenticated user, never from the request.
        return self.user.company_id

    @property
    def role(self) -> str:
        return self.user.role

    def can(self, permission: str) -> bool:
        return has_permission(self.role, permission)


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(settings.AUTH_COOKIE_NAME)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    token = _extract_token(request)
    if not token:
        raise Unauthorized("Authentication required.")
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError:
        raise Unauthorized("Session is invalid or has expired.")
    user = db.get(User, claims["sub"])
    if not user or not user.is_active or user.token_version != claims.get("tv"):
        raise Unauthorized("Session is invalid or has expired.")
    scope = claims.get("scp", "full")
    if scope == SCOPE_MFA_ENROLL and request.url.path not in MFA_ENROLL_ALLOWED:
        raise Forbidden("Set up two-factor authentication to continue.", code="mfa_enrollment_required")
    request.state.user_id = user.id
    return CurrentUser(user, scope)


def require(permission: str):
    def dep(current: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not current.can(permission):
            raise Forbidden("You do not have permission to perform this action.")
        return current
    return dep


def get_owned(db: Session, model: type[T], obj_id: str, company_id: str) -> T:
    """Fetch a tenant-owned row or 404. Never leaks existence across companies."""
    obj = db.scalar(select(model).where(model.id == obj_id, model.company_id == company_id))  # type: ignore[attr-defined]
    if obj is None:
        raise NotFound(f"{model.__name__} not found.")
    return obj
