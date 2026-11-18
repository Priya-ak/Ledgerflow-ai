# Testing guide

## What was executed in this build (9 Nov 2026)

| Suite | Command | Result |
|---|---|---|
| Backend unit + API tests on **SQLite** | `pytest` | **58 passed** |
| Same suite on **PostgreSQL 16** | `TEST_DATABASE_URL=postgresql://... pytest` | **58 passed** |
| Alembic upgrade / downgrade / drift check | `alembic upgrade head`, `alembic downgrade base`, `alembic check` | Passed on SQLite and PostgreSQL 16 |
| Demo seed through the real pipeline | `python -m app.demo.seed --reset` | 8 scenarios produce their expected outcomes (SQLite and PostgreSQL) |
| Frontend type check | `npm run typecheck` | No errors |
| Frontend lint | `npm run lint` | No warnings or errors |
| Frontend production build | `npm run build` | Succeeded (29 routes) |
| End-to-end (Playwright, Chromium) | `npm run test:e2e` | **9 passed** |

Not executed: the Docker image builds (the sandbox containers had no network to install Tesseract), any test against a real Ollama or Gemini model, and anything on Windows itself.

## Backend tests (`backend/tests`)

| File | Covers |
|---|---|
| `test_validation_engine.py` | Valid intra/inter-state invoices, wrong line tax (expected/actual/difference), grand-total mismatch, tolerance/round-off, missing fields, wrong GST regime both ways, future/due dates, negative quantity, GSTIN checksum, supplier GSTIN mismatch, duplicate context, input immutability, Decimal parsing |
| `test_extraction.py` | PDF text extraction of every field, OCR of PNG and noisy JPEG (skipped if Tesseract is missing), nulls instead of guesses, day-first dates, LLM grounding and schema validation, malformed LLM JSON, Ollama unreachable → rules, mocked Ollama API request contract, Gemini requires explicit opt-in |
| `test_po_matching.py` | Exact match with discount, price and quantity mismatch, extra items, supplier mismatch, tolerance |
| `test_api_auth.py` | Register/login/me/logout with token revocation, bad credentials, weak password, duplicate email, full password-reset flow with no account enumeration, tampered tokens, login rate limiting |
| `test_api_security.py` | Cross-company isolation (read, write, download, extract, attach), role permissions, last-admin protection, role change revokes sessions, spoofed/broken/empty/oversized uploads, filename traversal, immutable audit log, error envelope with request id |
| `test_api_workflow.py` | Upload → extract → correct → submit → approve with audit trail and analytics, self-approval block, reject with reason and resubmit, critical errors block approval, correction fixes validation, duplicate detection (number and checksum) and resolution, multi-level approval, manual PO re-match, missing-field completion, CRUD and listing, all Excel reports, system status, page preview and UTC timestamps |

```powershell
cd backend
.venv\Scripts\Activate.ps1      # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
pytest                           # SQLite, isolated temp database + storage
pytest tests/test_validation_engine.py -k gst   # a subset
# Against PostgreSQL (use a disposable database: tables are dropped and recreated)
$env:TEST_DATABASE_URL = "postgresql://user:pass@host:5432/ledgerflow_test"
pytest
```

The core suite never calls Ollama, Gemini or any network service. OCR tests are skipped automatically when Tesseract is not installed.

## End-to-end tests (`frontend/e2e`)

These need both servers running against a **freshly seeded** database. The workflow specs run serially and change data.

```bash
# terminal 1
cd backend && python -m app.demo.seed --reset && uvicorn app.main:app --port 8000
# terminal 2
cd frontend && npm run build && npm start
# terminal 3
cd frontend && npx playwright install chromium   # first time only
npm run test:e2e
```

Covered: public navigation, protected-route redirect, invalid login, registration, accountant upload with duplicate detection and document preview, correction and submission, approver approve and reject (with the reason requirement), approver access restrictions, admin audit log and Excel download.

## Optional AI tests

To try a real local model: start Ollama, pull `qwen2.5:0.5b-instruct`, set `AI_PROVIDER=ollama`, and upload `sample-data/synthetic-invoices/04_missing_fields.png`. The processing notes on the invoice show whether the model was used (`rules+ollama`) or the app fell back. If the model is unavailable or the machine runs out of memory, that is an environment limitation, not an application test failure.
