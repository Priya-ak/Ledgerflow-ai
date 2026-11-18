"""Company profile, company settings, approval policy and user management (Admin)."""
from __future__ import annotations

import secrets

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import CurrentUser, get_owned, require
from app.core.errors import BusinessRuleError, Conflict
from app.core.security import hash_password
from app.models import User
from app.models.enums import Role
from app.schemas.auth import CompanyOut, UserOut
from app.schemas.common import Page
from app.schemas.entities import ApprovalPolicyIO, CompanySettingsIO, CompanyUpdate, UserCreate, UserUpdate
from app.api.pagination import paginate
from app.services import audit
from app.services import mfa
from app.services.approvals import get_policy
from app.services.email import deliver, password_reset_email, security_notice_email
from app.services.invoices import company_settings

router = APIRouter(tags=["company & users"])


@router.get("/company", response_model=CompanyOut)
def get_company(current: CurrentUser = Depends(require("invoices:read"))):
    return current.user.company


@router.put("/company", response_model=CompanyOut)
def update_company(body: CompanyUpdate, request: Request, current: CurrentUser = Depends(require("company:manage")),
                   db: Session = Depends(get_db)):
    c = current.user.company
    changes = body.model_dump(exclude_unset=True)
    for k, v in changes.items():
        setattr(c, k, v)
    if "gstin" in changes:
        c.state_code = c.gstin[:2] if c.gstin else None
    audit.record(db, action="company.update", company_id=c.id, actor=current.user, entity_type="company",
                 entity_id=c.id, meta={"fields": list(changes)}, request=request)
    db.commit()
    return c


@router.get("/company/settings", response_model=CompanySettingsIO)
def get_settings(current: CurrentUser = Depends(require("invoices:read")), db: Session = Depends(get_db)):
    cs = company_settings(db, current.company_id)
    db.commit()
    return cs


@router.put("/company/settings", response_model=CompanySettingsIO)
def put_settings(body: CompanySettingsIO, request: Request, current: CurrentUser = Depends(require("settings:manage")),
                 db: Session = Depends(get_db)):
    cs = company_settings(db, current.company_id)
    turning_on_mfa = body.require_mfa and not cs.require_mfa
    for k, v in body.model_dump().items():
        setattr(cs, k, v)
    if turning_on_mfa:
        # Sign out everyone without MFA so their next login goes through enrolment.
        for u in db.scalars(select(User).where(User.company_id == current.company_id, User.mfa_enabled.is_(False))):
            if u.id != current.id:
                u.token_version += 1
    audit.record(db, action="settings.update", company_id=current.company_id, actor=current.user,
                 entity_type="company_settings", entity_id=cs.id, meta=body.model_dump(mode="json"), request=request)
    db.commit()
    return cs


@router.get("/company/approval-policy", response_model=ApprovalPolicyIO)
def get_approval_policy(current: CurrentUser = Depends(require("approvals:read")), db: Session = Depends(get_db)):
    p = get_policy(db, current.company_id)
    db.commit()
    return p


@router.put("/company/approval-policy", response_model=ApprovalPolicyIO)
def put_approval_policy(body: ApprovalPolicyIO, request: Request, current: CurrentUser = Depends(require("settings:manage")),
                        db: Session = Depends(get_db)):
    p = get_policy(db, current.company_id)
    data = body.model_dump(mode="json")
    p.levels, p.allow_self_approval, p.allow_critical_override = data["levels"], data["allow_self_approval"], data["allow_critical_override"]
    audit.record(db, action="approval_policy.update", company_id=current.company_id, actor=current.user,
                 entity_type="approval_policy", entity_id=p.id, meta=data, request=request)
    db.commit()
    return p


@router.get("/users", response_model=Page[UserOut])
def list_users(q: str | None = None, role: str | None = None, page: int = Query(1, ge=1),
               page_size: int = Query(50, ge=1, le=100), current: CurrentUser = Depends(require("users:read")),
               db: Session = Depends(get_db)):
    stmt = select(User).where(User.company_id == current.company_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(func.lower(User.email).like(like) | func.lower(User.full_name).like(like))
    if role:
        stmt = stmt.where(User.role == role)
    return paginate(db, stmt.order_by(User.created_at), page, page_size, UserOut)


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, request: Request, background: BackgroundTasks,
                current: CurrentUser = Depends(require("users:manage")), db: Session = Depends(get_db)):
    from app.api.auth import issue_reset  # local import avoids a router import cycle

    if db.scalar(select(User.id).where(func.lower(User.email) == body.email.lower())):
        raise Conflict("A user with this email already exists.")
    # Invited users get an unusable random password until they set their own.
    pw = body.password or secrets.token_urlsafe(48)[:64]
    u = User(company_id=current.company_id, email=body.email.lower(), full_name=body.full_name,
             role=body.role, password_hash=hash_password(pw))
    db.add(u)
    db.flush()
    raw = issue_reset(db, u, invite=True) if body.send_invite else None
    audit.record(db, action="user.create", company_id=current.company_id, actor=current.user, entity_type="user",
                 entity_id=u.id, meta={"email": u.email, "role": u.role, "invited": body.send_invite}, request=request)
    db.commit()
    if raw:
        background.add_task(deliver, password_reset_email(u.email, u.full_name, raw, invite=True, company_id=u.company_id,
                                                          user_id=u.id, company_name=current.user.company.name))
    return u


@router.post("/users/{user_id}/mfa/reset", response_model=UserOut)
def reset_user_mfa(user_id: str, request: Request, background: BackgroundTasks,
                   current: CurrentUser = Depends(require("users:manage")), db: Session = Depends(get_db)):
    """For a user who lost their phone and recovery codes. Signs them out everywhere."""
    u = get_owned(db, User, user_id, current.company_id)
    mfa.disable(db, u)
    u.token_version += 1
    audit.record(db, action="user.mfa_reset", company_id=current.company_id, actor=current.user, entity_type="user",
                 entity_id=u.id, meta={"email": u.email}, request=request)
    db.commit()
    background.add_task(deliver, security_notice_email(u.email, u.full_name,
                                                       event=f"two-factor authentication was reset by {current.user.full_name}",
                                                       company_id=u.company_id, user_id=u.id))
    return u


def _active_admins(db: Session, company_id: str) -> int:
    return db.scalar(select(func.count()).select_from(User).where(
        User.company_id == company_id, User.role == Role.ADMIN, User.is_active.is_(True))) or 0


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(user_id: str, body: UserUpdate, request: Request, current: CurrentUser = Depends(require("users:manage")),
                db: Session = Depends(get_db)):
    u = get_owned(db, User, user_id, current.company_id)
    changes = body.model_dump(exclude_unset=True)
    losing_admin = u.role == Role.ADMIN and (changes.get("role", u.role) != Role.ADMIN or changes.get("is_active") is False)
    if losing_admin and _active_admins(db, current.company_id) <= 1:
        raise BusinessRuleError("The company must keep at least one active admin.")
    before = {k: getattr(u, k) for k in changes}
    for k, v in changes.items():
        setattr(u, k, v)
    if "role" in changes or changes.get("is_active") is False:
        u.token_version += 1  # force re-login with new permissions
    audit.record(db, action="user.update", company_id=current.company_id, actor=current.user, entity_type="user",
                 entity_id=u.id, meta={"before": before, "after": changes}, request=request)
    db.commit()
    return u


@router.delete("/users/{user_id}", response_model=UserOut)
def deactivate_user(user_id: str, request: Request, current: CurrentUser = Depends(require("users:manage")),
                    db: Session = Depends(get_db)):
    """Users are deactivated, not deleted, so audit history stays attributable."""
    return update_user(user_id, UserUpdate(is_active=False), request, current, db)
