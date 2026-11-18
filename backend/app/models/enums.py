"""Domain enumerations stored as plain strings (portable across PostgreSQL/SQLite)."""
from enum import StrEnum


class Role(StrEnum):
    ADMIN = "admin"
    ACCOUNTANT = "accountant"
    APPROVER = "approver"


class InvoiceStatus(StrEnum):
    DRAFT = "draft"
    PROCESSING = "processing"
    EXTRACTED = "extracted"
    REVIEW_REQUIRED = "review_required"
    FAILED_PROCESSING = "failed_processing"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    ARCHIVED = "archived"


EDITABLE_STATUSES = {
    InvoiceStatus.DRAFT, InvoiceStatus.EXTRACTED, InvoiceStatus.REVIEW_REQUIRED,
    InvoiceStatus.FAILED_PROCESSING, InvoiceStatus.REJECTED,
}


class PaymentStatus(StrEnum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"


class ValidationStatus(StrEnum):
    NOT_RUN = "not_run"
    PASSED = "passed"
    WARNINGS = "warnings"
    FAILED = "failed"


class DuplicateStatus(StrEnum):
    NONE = "none"
    POSSIBLE = "possible_duplicate"
    DUPLICATE = "duplicate"
    RESOLVED_NOT_DUPLICATE = "resolved_not_duplicate"


class PoMatchStatus(StrEnum):
    NOT_RUN = "not_run"
    MATCHED = "matched"
    PARTIALLY_MATCHED = "partially_matched"
    MISMATCH = "mismatch"
    NO_PO_FOUND = "no_po_found"
    REQUIRES_REVIEW = "requires_review"


class SupplierStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    ARCHIVED = "archived"


class PoStatus(StrEnum):
    DRAFT = "draft"
    OPEN = "open"
    PARTIALLY_INVOICED = "partially_invoiced"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
