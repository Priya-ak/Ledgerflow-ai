# Technical and commercial review

An honest assessment of the MVP as delivered on 9 November 2026, scored against the handbook's 100-point rubric.

## Scorecard

| Area | Weight | Score | Rationale |
|---|---:|---:|---|
| Business value & ROI | 20 | **16** | Solves a real, frequent AP problem end to end (extract → validate → match → approve → report). Missing the integrations that create most of the ROI in practice: email ingestion and accounting export (Tally/Zoho Books) |
| Architecture & scalability | 15 | **12** | Clean modular monolith with clear service boundaries, portable across SQLite and PostgreSQL, and a pipeline ready to move to a worker. Synchronous processing and an in-process rate limiter cap throughput at one node |
| AI/ML implementation | 15 | **10** | Practical and safe: PyMuPDF/Tesseract with preprocessing, OCR-aware GSTIN repair gated by the check digit, schema-validated output, grounded LLM suggestions, graceful fallback. Extraction rules are proven only on synthetic layouts, there are no accuracy metrics on real invoices, and the LLM path was tested only against a mocked API |
| Backend & database | 15 | **13** | 18-table normalised schema, Alembic migrations verified up/down/check on SQLite and PostgreSQL 16, exact `Decimal` money, consistent error envelope, 57 documented endpoints, 58 passing tests on both databases |
| Frontend & UX | 10 | **8** | Professional, responsive, light/dark, role-aware navigation, side-by-side review, loading/empty/error states, 9 passing e2e tests. Not yet audited for accessibility; no bulk actions or keyboard shortcuts for high-volume reviewers |
| Security & reliability | 10 | **7** | Strong basics: bcrypt, httpOnly cookies with revocation, server-side RBAC and tenant isolation (tested), content-verified uploads, append-only audit, rate limits, safe errors. Gaps: no email delivery, MFA, CSP, malware scanning, DB-level audit immutability or backups |
| Testing & documentation | 10 | **9** | Unit, API, security, workflow and e2e tests, all executed. README covers all 30 required sections; architecture, data flow, ERD, API, security, environment, deployment, hardware and free-tier guides included |
| Deployment & demonstration | 5 | **2** | Demo mode, seed script, synthetic scenarios, screenshots and deployment configs exist, but no live URL and the Docker images were not built in this environment |
| **Total** | **100** | **77** | |

**Technical quality: 77/100.** A solid, honest MVP with production-grade foundations. It is not yet production-ready for a paying client.

## Architecture review
- **Strengths:** single responsibility per service (`validation`, `duplicates`, `po_matching`, `approvals`); pure, unit-tested engines; tenant scoping in one helper; storage and AI behind interfaces; migrations as the source of truth.
- **Risks:** analytics aggregate in Python (fine to tens of thousands of invoices); `processing_records.raw_text` grows the database (≤50 KB per document), so move it to storage at scale; the approvals list paginates in memory (cap 1,000).

## Code review highlights
- Money never touches `float` in business logic. SQLite stores exact text; the UI parses numbers only for display.
- Every state change writes an audit row in the same transaction.
- Corrections re-run all checks, so validation results can't go stale, and submission re-checks again.
- **Improve next:** add type checking (mypy/pyright) and ruff to CI; split `api/invoices.py` once more endpoints are added; add contract tests generated from `openapi.json`.

## AI/ML review
- The deterministic-first design is the right call for financial data and a 4 GB machine.
- **Accuracy is unmeasured on real documents.** Before selling, collect 50–100 real (consented, redacted) invoices per client, build a labelled set, and report field-level precision and recall. Expect to add supplier templates (keyed by supplier GSTIN) for the top suppliers by volume.
- A small LLM adds little to amounts. Its best use here is layout-agnostic header extraction, which is now safely constrained. A larger hosted model or a document-AI service would be an opt-in, client-funded upgrade with a data-processing agreement.

## Security gaps (prioritised)
1. Email delivery for password reset, plus MFA (or Supabase Auth / SSO).
2. Database role without UPDATE/DELETE on `audit_logs`; scheduled backups and a restore drill.
3. Malware scanning on upload; nonce-based CSP on the frontend.
4. Shared-store rate limiting; Sentry or OpenTelemetry for errors and traces.
5. DPDP Act readiness: retention policy, deletion workflow, processing records.

## Missing features vs. a typical paid deployment
Email/WhatsApp invoice ingestion · batch upload processing in the background · GRN / three-way match · accounting export (Tally XML, Zoho Books API, CSV for ERPs) · payment scheduling and due-date alerts · TDS handling · credit notes · GST portal verification through a licensed GSP · supplier portal · notifications (email/Slack) for approvers.

## Production-readiness assessment
| Ready | Needs work before production |
|---|---|
| Core workflow, validation engine, RBAC, tenant isolation, migrations, audit trail, reports | Email, MFA, backups, malware scan, CSP, monitoring, background processing, real-document accuracy validation, a paid hosting tier (Vercel Hobby is non-commercial; Render Free sleeps; Supabase Free pauses and has no backups) |

## Scalability limits
Single node, one document per request: roughly 2,000–5,000 invoices/day of mostly digital PDFs on a small server, far fewer if most are scans. To scale: background workers with a queue, object-storage-backed raw text, SQL-side analytics, a shared rate-limit store, and horizontal API replicas (the API is stateless apart from the rate limiter).

## Potential client types
- Manufacturing and engineering SMEs with 300–3,000 supplier invoices per month
- Distributors and trading companies with many GST suppliers
- CA and bookkeeping firms processing invoices for multiple clients (multi-company is already built in)
- Hospitals, schools and facility-management companies with high-volume, PO-driven purchasing

## Commercial value

**Illustrative ROI (assumptions, to be validated per client):** 1,000 invoices/month × 6 minutes of manual entry and checking is about 100 staff-hours/month. At a ₹300/hour loaded cost that is about ₹30,000/month. Saving 50–70% of that time is about ₹15,000–21,000/month, before counting avoided duplicate payments and GST errors (often the larger number).

**What justifies a ₹1 lakh+ customised implementation.** This is a target for a validated, customised deployment, not a price for the MVP as is:

| Work package | Why the client pays for it |
|---|---|
| Discovery + pilot on 50–100 of the client's real invoices, with an accuracy report | Proves value on *their* documents |
| Supplier-specific extraction templates for their top suppliers | Raises straight-through processing rates |
| Accounting integration (Tally / Zoho Books / ERP export) | Removes the second round of data entry |
| Email-inbox ingestion and approver notifications | Removes manual uploads and chasing |
| Their approval matrix, tolerances, roles and SSO/MFA | Fits their controls and auditors |
| Deployment on their cloud or on-prem server, with backups, monitoring and HTTPS | Production operation, not a demo |
| Training, documentation, 1–3 months of hypercare, then an AMC | Adoption and ongoing support |

A realistic structure is a fixed-fee implementation for the work above, plus an annual maintenance contract or per-invoice SaaS fee. Scope, integration complexity and support level determine the price.
