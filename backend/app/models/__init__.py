"""Import all models so Alembic and metadata see every table."""
from app.models.approval import ApprovalPolicy, ApprovalRequest, ApprovalStep
from app.models.audit import AuditLog
from app.models.document import Document, ProcessingRecord
from app.models.email_log import EmailLog
from app.models.invoice import DuplicateMatch, Invoice, InvoiceItem, PoMatchResult, ValidationResult
from app.models.organization import Company, CompanySettings
from app.models.purchase_order import PurchaseOrder, PurchaseOrderItem
from app.models.supplier import Supplier
from app.models.user import MfaRecoveryCode, PasswordResetToken, User

__all__ = [
    "ApprovalPolicy", "ApprovalRequest", "ApprovalStep", "AuditLog", "Company", "CompanySettings",
    "Document", "DuplicateMatch", "EmailLog", "MfaRecoveryCode", "Invoice", "InvoiceItem", "PasswordResetToken", "PoMatchResult",
    "ProcessingRecord", "PurchaseOrder", "PurchaseOrderItem", "Supplier", "User", "ValidationResult",
]
