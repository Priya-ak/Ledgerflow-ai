from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.schemas.common import ORM
from app.services.gst import normalize_gstin

Money = Decimal


def _gstin(v: str | None) -> str | None:
    return normalize_gstin(v)


# Users / company -------------------------------------------------------------
class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=200)
    role: Literal["admin", "accountant", "approver"]
    # Either email an invitation (user sets their own password) or set an initial password.
    send_invite: bool = False
    password: str | None = Field(default=None, min_length=10, max_length=72)

    @model_validator(mode="after")
    def _password_or_invite(self):
        if not self.send_invite and not self.password:
            raise ValueError("Provide an initial password or choose to send an invitation email.")
        return self


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    role: Literal["admin", "accountant", "approver"] | None = None
    is_active: bool | None = None


class CompanyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=200)
    gstin: str | None = Field(default=None, max_length=15)
    address: str | None = Field(default=None, max_length=1000)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    _g = field_validator("gstin")(classmethod(lambda cls, v: _gstin(v)))


class CompanySettingsIO(ORM):
    currency: str = Field(default="INR", min_length=3, max_length=3)
    amount_tolerance: Money = Field(default=Decimal("1.00"), ge=0, le=1000)
    po_price_tolerance_pct: Money = Field(default=Decimal("2.00"), ge=0, le=100)
    po_qty_tolerance_pct: Money = Field(default=Decimal("0.00"), ge=0, le=100)
    duplicate_window_days: int = Field(default=90, ge=1, le=730)
    require_mfa: bool = False
    notify_approvers: bool = True


class ApprovalLevel(BaseModel):
    level: int = Field(ge=1, le=5)
    name: str = Field(min_length=2, max_length=80)
    role: Literal["approver", "admin"]
    min_amount: Money = Field(default=Decimal("0"), ge=0)


class ApprovalPolicyIO(ORM):
    levels: list[ApprovalLevel] = Field(min_length=1, max_length=5)
    allow_self_approval: bool = False
    allow_critical_override: bool = False

    @field_validator("levels")
    @classmethod
    def _unique(cls, v):
        nums = [l.level for l in v]
        if len(set(nums)) != len(nums):
            raise ValueError("Approval levels must be unique.")
        return sorted(v, key=lambda l: l.level)


# Suppliers -------------------------------------------------------------------
class SupplierIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    code: str = Field(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_\-]+$")
    gstin: str | None = Field(default=None, max_length=20)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=1000)
    contact_person: str | None = Field(default=None, max_length=200)
    payment_terms_days: int = Field(default=30, ge=0, le=365)
    status: Literal["active", "inactive", "archived"] = "active"
    _g = field_validator("gstin")(classmethod(lambda cls, v: _gstin(v)))


class SupplierOut(ORM):
    id: str
    name: str
    code: str
    gstin: str | None
    email: str | None
    phone: str | None
    address: str | None
    contact_person: str | None
    payment_terms_days: int
    status: str
    created_at: datetime
    updated_at: datetime


class SupplierRef(ORM):
    id: str
    name: str
    code: str
    gstin: str | None


# Purchase orders -----------------------------------------------------------
class POItemIn(BaseModel):
    description: str = Field(min_length=1, max_length=500)
    hsn_sac: str | None = Field(default=None, max_length=10, pattern=r"^\d{4,8}$")
    quantity: Money = Field(gt=0)
    unit: str | None = Field(default=None, max_length=20)
    unit_price: Money = Field(ge=0)
    tax_rate: Money = Field(default=Decimal("0"), ge=0, le=100)


class POIn(BaseModel):
    supplier_id: str
    po_number: str = Field(min_length=1, max_length=60)
    po_date: date
    expected_delivery_date: date | None = None
    status: Literal["draft", "open", "partially_invoiced", "closed", "cancelled"] = "open"
    notes: str | None = Field(default=None, max_length=2000)
    items: list[POItemIn] = Field(min_length=1, max_length=200)


class POItemOut(ORM):
    id: str
    line_no: int
    description: str
    hsn_sac: str | None
    quantity: Money
    unit: str | None
    unit_price: Money
    tax_rate: Money
    line_total: Money


class POOut(ORM):
    id: str
    po_number: str
    supplier_id: str
    supplier: SupplierRef
    po_date: date
    expected_delivery_date: date | None
    currency: str
    subtotal: Money
    tax_total: Money
    total_amount: Money
    status: str
    notes: str | None
    created_at: datetime


class PODetail(POOut):
    items: list[POItemOut]


# Documents -----------------------------------------------------------------
class DocumentOut(ORM):
    scan_engine: str | None = None
    scan_result: str | None = None
    id: str
    invoice_id: str | None
    original_filename: str
    content_type: str
    size_bytes: int
    sha256: str
    page_count: int | None
    status: str
    error_message: str | None
    is_demo: bool
    created_at: datetime


# Invoices ------------------------------------------------------------------
class InvoiceItemIO(ORM):
    description: str | None = Field(default=None, max_length=500)
    hsn_sac: str | None = Field(default=None, max_length=10)
    quantity: Money | None = None
    unit: str | None = Field(default=None, max_length=20)
    unit_price: Money | None = None
    discount: Money | None = None
    taxable_value: Money | None = None
    tax_rate: Money | None = Field(default=None, ge=0, le=100)
    tax_amount: Money | None = None
    line_total: Money | None = None


class InvoiceIn(BaseModel):
    supplier_id: str | None = None
    purchase_order_id: str | None = None
    invoice_number: str | None = Field(default=None, max_length=60)
    invoice_date: date | None = None
    due_date: date | None = None
    po_number_ref: str | None = Field(default=None, max_length=60)
    currency: str = Field(default="INR", min_length=3, max_length=3)
    supplier_name_raw: str | None = Field(default=None, max_length=200)
    supplier_gstin_raw: str | None = Field(default=None, max_length=20)
    supplier_address_raw: str | None = Field(default=None, max_length=1000)
    buyer_name: str | None = Field(default=None, max_length=200)
    buyer_gstin: str | None = Field(default=None, max_length=20)
    buyer_address: str | None = Field(default=None, max_length=1000)
    subtotal: Money | None = None
    discount: Money | None = None
    taxable_amount: Money | None = None
    cgst: Money | None = None
    sgst: Money | None = None
    igst: Money | None = None
    other_charges: Money | None = None
    total_tax: Money | None = None
    grand_total: Money | None = None
    payment_status: Literal["unpaid", "partially_paid", "paid"] | None = None
    notes: str | None = Field(default=None, max_length=2000)
    items: list[InvoiceItemIO] | None = Field(default=None, max_length=200)
    _g = field_validator("supplier_gstin_raw", "buyer_gstin")(classmethod(lambda cls, v: _gstin(v)))


class InvoiceListItem(ORM):
    id: str
    invoice_number: str | None
    invoice_date: date | None
    due_date: date | None
    supplier_id: str | None
    supplier: SupplierRef | None
    supplier_name_raw: str | None
    grand_total: Money | None
    currency: str
    status: str
    payment_status: str
    validation_status: str
    duplicate_status: str
    po_match_status: str
    has_critical_errors: bool
    is_demo: bool
    created_at: datetime


class ApprovalStepOut(ORM):
    id: str
    level: int
    approver_id: str
    decision: str
    comment: str | None
    override_critical: bool
    created_at: datetime


class ApprovalRequestOut(ORM):
    id: str
    invoice_id: str
    submitted_by_id: str
    status: str
    current_level: int
    required_levels: list
    submission_note: str | None
    created_at: datetime
    completed_at: datetime | None
    steps: list[ApprovalStepOut]


class DuplicateMatchOut(ORM):
    id: str
    matched_invoice_id: str
    match_type: str
    score: int
    reasons: list
    resolution: str | None
    resolution_note: str | None
    resolved_at: datetime | None


class InvoiceDetail(InvoiceListItem):
    purchase_order_id: str | None
    po_number_ref: str | None
    supplier_gstin_raw: str | None
    supplier_address_raw: str | None
    buyer_name: str | None
    buyer_gstin: str | None
    buyer_address: str | None
    subtotal: Money | None
    discount: Money | None
    taxable_amount: Money | None
    cgst: Money | None
    sgst: Money | None
    igst: Money | None
    other_charges: Money | None
    total_tax: Money | None
    extraction_method: str | None
    needs_review_fields: list | None
    extracted_data: dict | None
    notes: str | None
    submitted_by_id: str | None
    submitted_at: datetime | None
    decided_at: datetime | None
    items: list[InvoiceItemIO]
    documents: list[DocumentOut]
    validation: dict | None = None
    po_match: dict | None = None
    duplicates: list[DuplicateMatchOut] = []
    approvals: list[ApprovalRequestOut] = []


class ExtractIn(BaseModel):
    document_id: str


class SubmitIn(BaseModel):
    note: str | None = Field(default=None, max_length=1000)


class ApproveIn(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)
    override_critical: bool = False


class RejectIn(BaseModel):
    reason: str = Field(min_length=5, max_length=2000)


class MatchPOIn(BaseModel):
    purchase_order_id: str | None = None


class ResolveDuplicateIn(BaseModel):
    resolution: Literal["not_duplicate", "confirmed_duplicate"]
    note: str = Field(min_length=5, max_length=1000)


class AuditLogOut(ORM):
    id: str
    actor_id: str | None
    actor_email: str | None
    action: str
    entity_type: str | None
    entity_id: str | None
    meta: dict | None
    ip_address: str | None
    created_at: datetime
