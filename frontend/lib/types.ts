export type Role = "admin" | "accountant" | "approver";
export type Money = string | null;

export interface Page<T> { items: T[]; total: number; page: number; page_size: number }

export interface User { id: string; email: string; full_name: string; role: Role; is_active: boolean; mfa_enabled: boolean; last_login_at: string | null; created_at: string }
export interface Company { id: string; name: string; gstin: string | null; address: string | null; state_code: string | null; email: string | null; phone: string | null; is_demo: boolean }
export interface MfaStatus { enabled: boolean; required_by_policy: boolean; enrollment_required: boolean; recovery_codes_remaining: number }
export interface Me { user: User; company: Company; permissions: string[]; mfa: MfaStatus }

export interface SupplierRef { id: string; name: string; code: string; gstin: string | null }
export interface Supplier extends SupplierRef {
  email: string | null; phone: string | null; address: string | null; contact_person: string | null;
  payment_terms_days: number; status: string; created_at: string; updated_at: string;
}

export interface POItem { id?: string; line_no?: number; description: string; hsn_sac: string | null; quantity: string; unit: string | null; unit_price: string; tax_rate: string; line_total?: string }
export interface PurchaseOrder {
  id: string; po_number: string; supplier_id: string; supplier: SupplierRef; po_date: string; expected_delivery_date: string | null;
  currency: string; subtotal: string; tax_total: string; total_amount: string; status: string; notes: string | null; created_at: string; items?: POItem[];
}

export interface DocumentInfo { id: string; invoice_id: string | null; scan_engine: string | null; scan_result: string | null; original_filename: string; content_type: string; size_bytes: number; sha256: string; page_count: number | null; status: string; error_message: string | null; is_demo: boolean; created_at: string }

export interface InvoiceItem { description: string | null; hsn_sac: string | null; quantity: Money; unit: string | null; unit_price: Money; discount: Money; taxable_value: Money; tax_rate: Money; tax_amount: Money; line_total: Money }

export interface InvoiceListItem {
  id: string; invoice_number: string | null; invoice_date: string | null; due_date: string | null; supplier_id: string | null;
  supplier: SupplierRef | null; supplier_name_raw: string | null; grand_total: Money; currency: string; status: string;
  payment_status: string; validation_status: string; duplicate_status: string; po_match_status: string; has_critical_errors: boolean;
  is_demo: boolean; created_at: string;
}

export interface Check {
  code: string; name: string; severity: "critical" | "warning" | "info"; passed: boolean; explanation: string;
  expected: string | null; actual: string | null; difference: string | null; recommended_action: string | null; line_no: number | null;
}
export interface ValidationReport { status: string; has_critical_errors: boolean; summary: { total: number; passed: number; critical_failures: number; warnings: number }; tolerance: { amount: string; line: string }; checks: Check[]; generated_at: string }

export interface PoDiff { field: string; invoice: string | null; po: string | null; difference: string | null }
export interface PoMatchReport {
  status: string; purchase_order: { id: string; po_number: string } | null; issues: string[];
  matched_items: { invoice_line: number; po_line: number; description: string; po_description: string; similarity: number; differences: PoDiff[]; status: string }[];
  extra_items: { invoice_line: number; description: string; amount: string | null }[];
  missing_items: { po_line: number; description: string; quantity: string }[];
  totals?: { invoice: string | null; po: string; difference: string | null; within_tolerance: boolean };
}

export interface DuplicateMatch { id: string; matched_invoice_id: string; match_type: string; score: number; reasons: string[]; resolution: string | null; resolution_note: string | null; resolved_at: string | null }
export interface ApprovalStep { id: string; level: number; approver_id: string; decision: string; comment: string | null; override_critical: boolean; created_at: string }
export interface ApprovalRequest { id: string; invoice_id: string; submitted_by_id: string; status: string; current_level: number; required_levels: { level: number; name: string; role: string; min_amount: string }[]; submission_note: string | null; created_at: string; completed_at: string | null; steps: ApprovalStep[] }

export interface InvoiceDetail extends InvoiceListItem {
  purchase_order_id: string | null; po_number_ref: string | null; supplier_gstin_raw: string | null; supplier_address_raw: string | null;
  buyer_name: string | null; buyer_gstin: string | null; buyer_address: string | null;
  subtotal: Money; discount: Money; taxable_amount: Money; cgst: Money; sgst: Money; igst: Money; other_charges: Money; total_tax: Money;
  extraction_method: string | null; needs_review_fields: string[] | null;
  extracted_data: { extraction_metadata?: { method: string; text_method: string | null; ocr_confidence: number | null; warnings: string[]; ai_suggested_fields: string[] } } | null;
  notes: string | null; submitted_by_id: string | null; submitted_at: string | null; decided_at: string | null;
  items: InvoiceItem[]; documents: DocumentInfo[]; validation: ValidationReport | null; po_match: PoMatchReport | null;
  duplicates: DuplicateMatch[]; approvals: ApprovalRequest[];
}

export interface AuditLog { id: string; actor_id: string | null; actor_email: string | null; action: string; entity_type: string | null; entity_id: string | null; meta: Record<string, unknown> | null; ip_address: string | null; created_at: string }

export interface ApprovalListItem extends ApprovalRequest { invoice: InvoiceListItem; can_decide: boolean }
