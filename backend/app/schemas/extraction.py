"""Structured extraction schema. Every extractor (rules / LLM) must produce this."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ExtractedParty(_M):
    name: str | None = None
    gstin: str | None = None
    address: str | None = None
    contact: str | None = None


class ExtractedInvoiceHeader(_M):
    invoice_number: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    purchase_order_number: str | None = None
    currency: str | None = None


class ExtractedItem(_M):
    description: str | None = None
    hsn_sac: str | None = None
    quantity: Decimal | None = None
    unit: str | None = None
    unit_price: Decimal | None = None
    discount: Decimal | None = None
    taxable_value: Decimal | None = None
    tax_rate: Decimal | None = None
    tax_amount: Decimal | None = None
    line_total: Decimal | None = None


class ExtractedSummary(_M):
    subtotal: Decimal | None = None
    discount: Decimal | None = None
    taxable_total: Decimal | None = None
    cgst: Decimal | None = None
    sgst: Decimal | None = None
    igst: Decimal | None = None
    total_tax: Decimal | None = None
    other_charges: Decimal | None = None
    grand_total: Decimal | None = None


class ExtractionMetadata(_M):
    method: str = "rules"
    text_method: str | None = None
    ocr_confidence: float | None = None
    needs_review: bool = True
    review_fields: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    ai_suggested_fields: list[str] = Field(default_factory=list)


class ExtractedInvoice(_M):
    supplier: ExtractedParty = Field(default_factory=ExtractedParty)
    invoice: ExtractedInvoiceHeader = Field(default_factory=ExtractedInvoiceHeader)
    buyer: ExtractedParty = Field(default_factory=ExtractedParty)
    items: list[ExtractedItem] = Field(default_factory=list)
    summary: ExtractedSummary = Field(default_factory=ExtractedSummary)
    extraction_metadata: ExtractionMetadata = Field(default_factory=ExtractionMetadata)


class LlmHeaderSuggestion(_M):
    """What an LLM is allowed to suggest: identifying fields only, never amounts."""

    invoice_number: str | None = Field(default=None, max_length=60)
    invoice_date: str | None = Field(default=None, max_length=30)
    due_date: str | None = Field(default=None, max_length=30)
    purchase_order_number: str | None = Field(default=None, max_length=60)
    supplier_name: str | None = Field(default=None, max_length=200)
    supplier_gstin: str | None = Field(default=None, max_length=20)
    buyer_name: str | None = Field(default=None, max_length=200)
    buyer_gstin: str | None = Field(default=None, max_length=20)
