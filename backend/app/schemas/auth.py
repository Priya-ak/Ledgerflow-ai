from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.common import ORM


def _strong(pw: str) -> str:
    if len(pw) < 10 or not any(c.isdigit() for c in pw) or not any(c.isalpha() for c in pw):
        raise ValueError("Password must be at least 10 characters and contain letters and digits.")
    return pw


class RegisterIn(BaseModel):
    company_name: str = Field(min_length=2, max_length=200)
    full_name: str = Field(min_length=2, max_length=200)
    email: EmailStr
    password: str = Field(max_length=72)
    gstin: str | None = Field(default=None, max_length=15)

    _pw = field_validator("password")(classmethod(lambda cls, v: _strong(v)))


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)


class ForgotIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(max_length=72)

    _pw = field_validator("new_password")(classmethod(lambda cls, v: _strong(v)))


class CompanyOut(ORM):
    id: str
    name: str
    gstin: str | None
    address: str | None
    state_code: str | None
    email: str | None
    phone: str | None
    is_demo: bool


class UserOut(ORM):
    id: str
    email: str
    full_name: str
    role: str
    is_active: bool
    mfa_enabled: bool = False
    last_login_at: datetime | None
    created_at: datetime


class MfaStatus(BaseModel):
    enabled: bool
    required_by_policy: bool
    enrollment_required: bool
    recovery_codes_remaining: int = 0


class MeOut(BaseModel):
    user: UserOut
    company: CompanyOut
    permissions: list[str]
    mfa: MfaStatus


class LoginOut(MeOut):
    access_token: str
    token_type: str = "bearer"
    mfa_required: bool = False


class MfaChallengeOut(BaseModel):
    mfa_required: bool = True
    mfa_token: str
    message: str = "Enter the 6-digit code from your authenticator app, or a recovery code."


class MfaVerifyIn(BaseModel):
    mfa_token: str = Field(min_length=20, max_length=1000)
    code: str = Field(min_length=6, max_length=20)


class MfaSetupOut(BaseModel):
    secret: str
    otpauth_uri: str
    qr_svg: str


class MfaCodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=20)


class MfaDisableIn(BaseModel):
    password: str = Field(min_length=1, max_length=72)
    code: str = Field(min_length=6, max_length=20)


class RecoveryCodesOut(BaseModel):
    recovery_codes: list[str]
    message: str = "Store these one-time recovery codes somewhere safe. They are shown only once."


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(max_length=72)

    _pw = field_validator("new_password")(classmethod(lambda cls, v: _strong(v)))


class ForgotOut(BaseModel):
    message: str
    dev_reset_token: str | None = None
