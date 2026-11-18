# Database design (ERD)

Schema is managed by **Alembic** (`backend/alembic/versions/0001_initial_schema.py`). `database/schema.sql` is the same migration rendered as PostgreSQL DDL for review. All primary keys are UUID strings, so data is portable between SQLite and PostgreSQL.

```mermaid
erDiagram
    companies ||--|| company_settings : has
    companies ||--|| approval_policies : has
    companies ||--o{ users : employs
    companies ||--o{ suppliers : buys_from
    companies ||--o{ purchase_orders : issues
    companies ||--o{ invoices : receives
    companies ||--o{ documents : stores
    companies ||--o{ audit_logs : records
    users ||--o{ password_reset_tokens : requests
    suppliers ||--o{ purchase_orders : "fulfils"
    suppliers ||--o{ invoices : bills
    purchase_orders ||--o{ purchase_order_items : contains
    purchase_orders ||--o{ invoices : "referenced by"
    invoices ||--o{ invoice_items : contains
    invoices ||--o{ documents : "original file(s)"
    invoices ||--o{ validation_results : "validated (history)"
    invoices ||--o{ po_match_results : "matched (history)"
    invoices ||--o{ duplicate_matches : flags
    invoices ||--o{ approval_requests : submitted
    approval_requests ||--o{ approval_steps : decisions
    documents ||--o{ processing_records : "pipeline runs"

    companies { string id PK  string name  string gstin  string state_code  bool is_demo }
    company_settings { string company_id FK,UK  numeric amount_tolerance  numeric po_price_tolerance_pct  numeric po_qty_tolerance_pct  int duplicate_window_days }
    approval_policies { string company_id FK,UK  json levels  bool allow_self_approval  bool allow_critical_override }
    users { string id PK  string company_id FK  string email UK  string password_hash  string role  bool is_active  int token_version }
    suppliers { string id PK  string company_id FK  string code  string name  string gstin  int payment_terms_days  string status }
    purchase_orders { string id PK  string company_id FK  string supplier_id FK  string po_number  date po_date  numeric total_amount  string status }
    purchase_order_items { string id PK  string purchase_order_id FK  string description  string hsn_sac  numeric quantity  numeric unit_price  numeric tax_rate }
    invoices { string id PK  string company_id FK  string supplier_id FK  string purchase_order_id FK  string invoice_number  string invoice_number_normalized  date invoice_date  numeric taxable_amount  numeric cgst  numeric sgst  numeric igst  numeric grand_total  string status  string validation_status  string duplicate_status  string po_match_status  bool has_critical_errors  json extracted_data }
    invoice_items { string id PK  string invoice_id FK  int line_no  string description  numeric quantity  numeric unit_price  numeric taxable_value  numeric tax_rate  numeric tax_amount  numeric line_total }
    documents { string id PK  string company_id FK  string invoice_id FK  string storage_key UK  string content_type  bigint size_bytes  string sha256  string status }
    processing_records { string id PK  string document_id FK  string status  string text_method  float ocr_confidence  int duration_ms  text raw_text }
    validation_results { string id PK  string invoice_id FK  string status  json report }
    po_match_results { string id PK  string invoice_id FK  string purchase_order_id FK  string status  json report }
    duplicate_matches { string id PK  string invoice_id FK  string matched_invoice_id FK  string match_type  int score  json reasons  string resolution }
    approval_requests { string id PK  string invoice_id FK  string submitted_by_id FK  string status  int current_level  json required_levels }
    approval_steps { string id PK  string request_id FK  int level  string approver_id FK  string decision  text comment  bool override_critical }
    audit_logs { string id PK  string company_id FK  string actor_id FK  string action  string entity_type  string entity_id  json metadata  datetime created_at }
    password_reset_tokens { string id PK  string user_id FK  string token_hash UK  datetime expires_at  datetime used_at }
```

## Constraints and indexes

| Rule | Implementation |
|---|---|
| One account per email | `uq_users_email` |
| Supplier code unique per company | `uq_supplier_company_code` |
| PO number unique per company | `uq_po_company_number` |
| Storage key unique | `documents.storage_key` UNIQUE |
| Fast duplicate lookups | `ix_invoice_dup_lookup (company_id, supplier_id, invoice_number_normalized)` + `documents.sha256` index |
| Fast dashboard filters | `ix_invoice_company_status`, `ix_invoice_company_date`, `ix_audit_company_created` |
| Referential integrity | Foreign keys everywhere; `ON DELETE CASCADE` from company; SQLite runs with `PRAGMA foreign_keys=ON` |
| Money precision | `NUMERIC(18,2)` (quantities `NUMERIC(18,3)`) on PostgreSQL; exact TEXT on SQLite via the `Money` type |
| Timestamps | `TIMESTAMPTZ`, always UTC (`UTCDateTime` type guarantees tz-aware values on SQLite too) |

Invoice-number uniqueness is deliberately **not** a database constraint: duplicates must be stored and shown to a person, not rejected at upload.

## Migrations

```bash
cd backend
alembic upgrade head                 # apply
alembic downgrade -1                 # roll back one revision
alembic revision --autogenerate -m "describe change"   # after editing models; review the file before committing
alembic check                        # fails if models and migrations differ
```

Verified in this build: `upgrade`, `downgrade base` and `check` on both SQLite and PostgreSQL 16.

## Row-level security note

Tenant isolation is enforced in the API layer, and the backend connects with a single database role. If you expose the Supabase database directly to clients (e.g. via PostgREST), you **must** enable Row Level Security policies on every table first. LedgerFlow does not need that exposure, so keep the database private.
