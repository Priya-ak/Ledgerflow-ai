export interface Overview {
  total_invoices: number; total_value: string; approved_count: number; approved_amount: string; pending_count: number; pending_amount: string;
  rejected_count: number; rejected_amount: string; review_required_count: number; ready_to_submit_count: number; failed_processing_count: number;
  duplicate_count: number; validation_exception_count: number; active_suppliers: number; open_purchase_orders: number;
  status_distribution: { status: string; count: number }[];
}
export interface InvoiceTrends { monthly: { month: string; count: number; value: string; approved_value: string }[]; validation_issues: { issue: string; count: number }[] }
export interface ApprovalTrends {
  monthly: { month: string; approved: number; rejected: number }[]; average_hours_to_decision: number | null;
  high_value_pending: { id: string; invoice_number: string | null; grand_total: string; supplier: string | null; submitted_at: string | null }[];
  my_decisions: Record<string, number>;
}
export interface SupplierStats { suppliers: { supplier_id: string; name: string; invoice_count: number; total: string; exceptions: number }[] }
