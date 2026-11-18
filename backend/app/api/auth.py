from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import CurrentUser, get_current_user
from app.core.errors import BusinessRuleError, Conflict, Unauthorized
from app.core.permissions import permissions_for
from app.core.ratelimit import limiter, rate_limit
from app.core.security import (
    SCOPE_FULL, SCOPE_MFA_ENROLL, create_access_token, create_mfa_challenge_token, decode_mfa_challenge_token,
    hash_password, hash_reset_token, new_reset_token, verify_password,
)
from app.models import Company, CompanySettings, PasswordResetToken, User
from app.models.enums import Role
from app.schemas.auth import (
    ChangePasswordIn, CompanyOut, ForgotIn, ForgotOut, LoginIn, LoginOut, MeOut, MfaChallengeOut, MfaCodeIn,
    MfaDisableIn, MfaSetupOut, MfaStatus, MfaVerifyIn, RecoveryCodesOut, RegisterIn, ResetIn, UserOut,
)
from app.schemas.common import Message
from app.services import audit, mfa
from app.services.approvals import get_policy
from app.services.email import deliver, password_reset_email, security_notice_email
from app.services.gst import normalize_gstin
from app.services.invoices import company_settings

router = APIRouter(prefix="/auth", tags=["auth"])

# Constant-time-ish dummy hash so unknown emails take as long as wrong passwords.
_DUMMY_HASH = hash_password("dummy-password-0")


def _set_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(settings.AUTH_COOKIE_NAME, token, httponly=True, secure=settings.AUTH_COOKIE_SECURE,
                    samesite="lax", max_age=settings.JWT_EXPIRE_MINUTES * 60, path="/")


def _mfa_required_by_policy(db: Session, user: User) -> bool:
    return company_settings(db, user.company_id).require_mfa


def _me(db: Session, user: User, scope: str = SCOPE_FULL) -> dict:
    required = _mfa_required_by_policy(db, user)
    return {
        "user": UserOut.model_validate(user), "company": CompanyOut.model_validate(user.company),
        "permissions": [] if scope == SCOPE_MFA_ENROLL else permissions_for(user.role),
        "mfa": MfaStatus(enabled=user.mfa_enabled, required_by_policy=required,
                         enrollment_required=required and not user.mfa_enabled,
                         recovery_codes_remaining=mfa.remaining_recovery_codes(db, user) if user.mfa_enabled else 0),
    }


def _issue_session(db: Session, user: User, response: Response) -> dict:
    scope = SCOPE_MFA_ENROLL if (_mfa_required_by_policy(db, user) and not user.mfa_enabled) else SCOPE_FULL
    token = create_access_token(user.id, user.company_id, user.role, user.token_version, scope)
    _set_cookie(response, token)
    return {**_me(db, user, scope), "access_token": token}


def _can_show_dev_token() -> bool:
    return settings.APP_ENV in ("development", "test") and settings.DEMO_MODE and settings.EMAIL_PROVIDER in ("console", "none")


@router.post("/register", response_model=LoginOut, status_code=201,
             dependencies=[Depends(rate_limit("register", 5, 3600))])
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Create a new company workspace with its first Admin user."""
    email = body.email.lower()
    if db.scalar(select(User.id).where(func.lower(User.email) == email)):
        raise Conflict("An account with this email already exists.")
    g = normalize_gstin(body.gstin)
    company = Company(name=body.company_name.strip(), gstin=g, state_code=g[:2] if g else None)
    db.add(company)
    db.flush()
    db.add(CompanySettings(company_id=company.id))
    get_policy(db, company.id)
    user = User(company_id=company.id, email=email, full_name=body.full_name.strip(),
                password_hash=hash_password(body.password), role=Role.ADMIN)
    db.add(user)
    db.flush()
    audit.record(db, action="auth.register", company_id=company.id, actor=user, entity_type="company",
                 entity_id=company.id, request=request)
    db.commit()
    return _issue_session(db, user, response)


@router.post("/login", response_model=LoginOut | MfaChallengeOut, dependencies=[Depends(rate_limit("login", 30, 300))])
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    # Per-IP limit is loose (offices share one NAT IP); the per-account limit stops brute force.
    limiter.check(f"login-account:{body.email.lower()}", 10, 900)
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower()))
    if user is None:
        verify_password(body.password, _DUMMY_HASH)
        raise Unauthorized("Invalid email or password.")
    if not verify_password(body.password, user.password_hash) or not user.is_active:
        audit.record(db, action="auth.login_failed", company_id=user.company_id, actor=user, request=request)
        db.commit()
        raise Unauthorized("Invalid email or password.")
    if user.mfa_enabled:
        audit.record(db, action="auth.mfa_challenge", company_id=user.company_id, actor=user, request=request)
        db.commit()
        return MfaChallengeOut(mfa_token=create_mfa_challenge_token(user.id, user.token_version))
    user.last_login_at = datetime.now(timezone.utc)
    audit.record(db, action="auth.login", company_id=user.company_id, actor=user, request=request)
    db.commit()
    return _issue_session(db, user, response)


@router.post("/mfa/verify", response_model=LoginOut, dependencies=[Depends(rate_limit("mfa-verify", 10, 300))])
def mfa_verify(body: MfaVerifyIn, request: Request, response: Response, db: Session = Depends(get_db)):
    """Second login step: TOTP code or one-time recovery code."""
    try:
        claims = decode_mfa_challenge_token(body.mfa_token)
    except jwt.PyJWTError:
        raise Unauthorized("The sign-in attempt expired. Please sign in again.")
    user = db.get(User, claims["sub"])
    if not user or not user.is_active or user.token_version != claims.get("tv"):
        raise Unauthorized("The sign-in attempt expired. Please sign in again.")
    limiter.check(f"mfa-user:{user.id}", 5, 300)  # per-account guard against code guessing
    method = mfa.verify_login(db, user, body.code)
    if method is None:
        audit.record(db, action="auth.mfa_failed", company_id=user.company_id, actor=user, request=request)
        db.commit()
        raise Unauthorized("Invalid or already-used code.")
    user.last_login_at = datetime.now(timezone.utc)
    audit.record(db, action="auth.login", company_id=user.company_id, actor=user, request=request,
                 meta={"mfa": method, "recovery_codes_left": mfa.remaining_recovery_codes(db, user) - (method == "recovery_code")})
    db.commit()
    return _issue_session(db, user, response)


@router.post("/logout", response_model=Message)
def logout(request: Request, response: Response, current: CurrentUser = Depends(get_current_user),
           db: Session = Depends(get_db)):
    """Invalidates all of the user's issued tokens (token_version bump) and clears the cookie."""
    current.user.token_version += 1
    audit.record(db, action="auth.logout", company_id=current.company_id, actor=current.user, request=request)
    db.commit()
    response.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")
    return {"message": "Logged out."}


@router.get("/me", response_model=MeOut)
def me(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _me(db, current.user, current.scope)


# ------------------------------------------------------------------ two-factor management
@router.get("/mfa", response_model=MfaStatus)
def mfa_status(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    return _me(db, current.user, current.scope)["mfa"]


@router.post("/mfa/setup", response_model=MfaSetupOut)
def mfa_setup(request: Request, current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    if current.user.mfa_enabled:
        raise BusinessRuleError("Two-factor authentication is already enabled.")
    data = mfa.begin_setup(current.user)
    audit.record(db, action="auth.mfa_setup_started", company_id=current.company_id, actor=current.user, request=request)
    db.commit()
    return data


@router.post("/mfa/enable", response_model=RecoveryCodesOut, dependencies=[Depends(rate_limit("mfa-enable", 10, 300))])
def mfa_enable(body: MfaCodeIn, request: Request, response: Response, background: BackgroundTasks,
               current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = current.user
    codes = mfa.confirm_setup(db, user, body.code)
    if codes is None:
        raise BusinessRuleError("That code didn't match. Check the time on your phone and try again.")
    user.token_version += 1  # sign out other sessions; re-issue a full session for this one
    audit.record(db, action="auth.mfa_enabled", company_id=current.company_id, actor=user, request=request)
    db.commit()
    _set_cookie(response, create_access_token(user.id, user.company_id, user.role, user.token_version, SCOPE_FULL))
    background.add_task(deliver, security_notice_email(user.email, user.full_name, event="two-factor authentication was turned on",
                                                       company_id=user.company_id, user_id=user.id))
    return {"recovery_codes": codes}


@router.post("/mfa/disable", response_model=Message, dependencies=[Depends(rate_limit("mfa-disable", 5, 300))])
def mfa_disable(body: MfaDisableIn, request: Request, background: BackgroundTasks,
                current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = current.user
    if _mfa_required_by_policy(db, user):
        raise BusinessRuleError("Your company requires two-factor authentication; it cannot be turned off.")
    if not verify_password(body.password, user.password_hash) or mfa.verify_login(db, user, body.code) is None:
        db.commit()  # persist recovery-code consumption / replay step if any
        raise Unauthorized("Password or code is incorrect.")
    mfa.disable(db, user)
    audit.record(db, action="auth.mfa_disabled", company_id=current.company_id, actor=user, request=request)
    db.commit()
    background.add_task(deliver, security_notice_email(user.email, user.full_name, event="two-factor authentication was turned off",
                                                       company_id=user.company_id, user_id=user.id))
    return {"message": "Two-factor authentication disabled."}


@router.post("/mfa/recovery-codes", response_model=RecoveryCodesOut, dependencies=[Depends(rate_limit("mfa-codes", 5, 300))])
def mfa_recovery_codes(body: MfaCodeIn, request: Request, current: CurrentUser = Depends(get_current_user),
                       db: Session = Depends(get_db)):
    user = current.user
    if not user.mfa_enabled or mfa.verify_login(db, user, body.code) != "totp":
        db.commit()
        raise Unauthorized("Enter a current code from your authenticator app.")
    codes = mfa.regenerate_recovery_codes(db, user)
    audit.record(db, action="auth.mfa_recovery_codes_regenerated", company_id=current.company_id, actor=user, request=request)
    db.commit()
    return {"recovery_codes": codes}


# ------------------------------------------------------------------ passwords
@router.post("/change-password", response_model=Message, dependencies=[Depends(rate_limit("change-pw", 5, 300))])
def change_password(body: ChangePasswordIn, request: Request, response: Response, background: BackgroundTasks,
                    current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    user = current.user
    if not verify_password(body.current_password, user.password_hash):
        raise Unauthorized("Current password is incorrect.")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    audit.record(db, action="auth.password_changed", company_id=user.company_id, actor=user, request=request)
    db.commit()
    _set_cookie(response, create_access_token(user.id, user.company_id, user.role, user.token_version, current.scope))
    background.add_task(deliver, security_notice_email(user.email, user.full_name, event="your password was changed",
                                                       company_id=user.company_id, user_id=user.id))
    return {"message": "Password changed. Other sessions were signed out."}


def issue_reset(db: Session, user: User, *, invite: bool) -> str:
    raw, hashed = new_reset_token()
    ttl = timedelta(hours=72) if invite else timedelta(minutes=30)
    db.add(PasswordResetToken(user_id=user.id, token_hash=hashed, expires_at=datetime.now(timezone.utc) + ttl))
    return raw


@router.post("/forgot-password", response_model=ForgotOut, dependencies=[Depends(rate_limit("forgot", 5, 3600))])
def forgot_password(body: ForgotIn, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Always returns the same message (no account enumeration). The email is sent after the response."""
    generic = "If an account exists for this email, password reset instructions have been sent."
    user = db.scalar(select(User).where(func.lower(User.email) == body.email.lower(), User.is_active.is_(True)))
    if user is None:
        return {"message": generic}
    raw = issue_reset(db, user, invite=False)
    audit.record(db, action="auth.password_reset_requested", company_id=user.company_id, actor=user, request=request)
    db.commit()
    background.add_task(deliver, password_reset_email(user.email, user.full_name, raw, invite=False,
                                                      company_id=user.company_id, user_id=user.id))
    return {"message": generic, "dev_reset_token": raw if _can_show_dev_token() else None}


@router.post("/reset-password", response_model=Message, dependencies=[Depends(rate_limit("reset", 10, 3600))])
def reset_password(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    rec = db.scalar(select(PasswordResetToken).where(PasswordResetToken.token_hash == hash_reset_token(body.token)))
    now = datetime.now(timezone.utc)
    if rec is None or rec.used_at is not None or rec.expires_at < now:
        raise BusinessRuleError("This reset link is invalid or has expired.")
    user = db.get(User, rec.user_id)
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1  # sign out all sessions
    rec.used_at = now
    audit.record(db, action="auth.password_reset", company_id=user.company_id, actor=user, request=request)
    db.commit()
    return {"message": "Password updated. Please sign in."}
