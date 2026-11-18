# Data flow

## Document → approved invoice

```mermaid
sequenceDiagram
    autonumber
    actor A as Accountant
    participant UI as Next.js UI
    participant API as FastAPI
    participant S as Storage
    participant T as PyMuPDF / Tesseract
    participant R as Rule extractor
    participant L as LLM (optional)
    participant C as Checks (dup · PO · validation)
    participant DB as Database
    actor P as Approver

    A->>UI: Drop PDF/JPG/PNG
    UI->>API: POST /documents/upload (multipart, streamed)
    API->>API: size limit, magic-byte sniff, extension match, parser check, SHA-256
    API->>S: save as companies/{cid}/documents/{uuid}.{ext}
    API->>DB: documents row + audit(document.upload)
    UI->>API: POST /invoices/extract {document_id}
    API->>T: text per page (PDF text layer, else OCR one page at a time)
    T-->>API: lines + OCR confidence
    API->>R: regex/label extraction → ExtractedInvoice (Pydantic)
    opt AI_PROVIDER = ollama | gemini
        API->>L: missing identifier fields only (≤2,500 chars, JSON mode)
        L-->>API: suggestions → schema-validated → kept only if found verbatim in text
    end
    API->>DB: invoice + items (supplier & PO resolved from master data)
    API->>C: duplicates → PO match → Decimal validation
    C->>DB: duplicate_matches, po_match_results, validation_results
    API-->>UI: invoice detail (status extracted / review_required)
    A->>UI: Compare with original, correct fields
    UI->>API: PUT /invoices/{id} → checks re-run, audit(invoice.correct, field diff)
    A->>API: POST /invoices/{id}/submit → approval_request (levels by amount)
    P->>API: POST /invoices/{id}/approve | reject (reason required)
    API->>API: segregation of duties, critical-error block, level progression
    API->>DB: approval_steps + audit, invoice → approved or rejected
```

## Invoice lifecycle

```mermaid
stateDiagram-v2
    [*] --> processing: extract
    processing --> extracted: all checks passed, nothing to review
    processing --> review_required: warnings / failures / missing fields
    processing --> failed_processing: unreadable document
    [*] --> draft: manual entry
    draft --> extracted
    draft --> review_required
    failed_processing --> review_required: manual correction
    review_required --> extracted: corrected and clean
    extracted --> pending_approval: submit
    review_required --> pending_approval: submit (no exact duplicate, required fields present)
    pending_approval --> pending_approval: level N approved, level N+1 required
    pending_approval --> approved: final level approved (no critical errors)
    pending_approval --> rejected: rejected with reason
    rejected --> review_required: corrected
    review_required --> archived
    extracted --> archived
    approved --> archived
    rejected --> archived
```

Each invoice also carries three independent statuses shown as badges:

- `validation_status`: `not_run`, `passed`, `warnings` or `failed`. `has_critical_errors` blocks approval.
- `duplicate_status`: `none`, `possible_duplicate`, `duplicate` or `resolved_not_duplicate`. An exact duplicate blocks submission.
- `po_match_status`: `not_run`, `matched`, `partially_matched`, `mismatch`, `no_po_found` or `requires_review`.

## What is stored

| Artefact | Where | Mutable? |
|---|---|---|
| Original file | Storage (`storage_key`), metadata in `documents` | No (delete is admin-only and blocked for pending/approved invoices) |
| OCR/PDF text | `processing_records.raw_text` (≤50k chars) | No |
| Extraction snapshot | `invoices.extracted_data` (JSON) | No; corrections go to invoice columns |
| Current invoice values | `invoices`, `invoice_items` | Yes, while editable; every change is audited |
| Validation / PO / duplicate results | `validation_results`, `po_match_results`, `duplicate_matches` (history kept) | Append-only history |
| Decisions | `approval_requests`, `approval_steps` | Steps are append-only |
| Audit trail | `audit_logs` | Append-only (ORM blocks update/delete) |
