"""Role -> permission mapping. Enforced on the backend for every protected route."""
from __future__ import annotations

from app.models.enums import Role

P = {
    "company:manage": {Role.ADMIN},
    "users:manage": {Role.ADMIN},
    "users:read": {Role.ADMIN},
    "settings:manage": {Role.ADMIN},
    "suppliers:read": {Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER},
    "suppliers:write": {Role.ADMIN, Role.ACCOUNTANT},
    "suppliers:delete": {Role.ADMIN},
    "po:read": {Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER},
    "po:write": {Role.ADMIN, Role.ACCOUNTANT},
    "po:delete": {Role.ADMIN},
    "invoices:read": {Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER},
    "invoices:write": {Role.ADMIN, Role.ACCOUNTANT},
    "invoices:delete": {Role.ADMIN},
    "invoices:submit": {Role.ADMIN, Role.ACCOUNTANT},
    "documents:upload": {Role.ADMIN, Role.ACCOUNTANT},
    "documents:read": {Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER},
    "documents:delete": {Role.ADMIN},
    "duplicates:resolve": {Role.ADMIN, Role.ACCOUNTANT},
    "approvals:read": {Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER},
    "approvals:decide": {Role.ADMIN, Role.APPROVER},
    "approvals:override": {Role.ADMIN},
    "analytics:read": {Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER},
    "reports:export": {Role.ADMIN, Role.ACCOUNTANT, Role.APPROVER},
    "audit:read": {Role.ADMIN},
}


def has_permission(role: str, permission: str) -> bool:
    return role in P.get(permission, set())


def permissions_for(role: str) -> list[str]:
    return sorted(p for p, roles in P.items() if role in roles)
