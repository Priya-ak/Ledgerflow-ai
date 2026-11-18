# Hardware limitations (Windows 11 · 4 GB RAM · no GPU)

LedgerFlow was designed to run on that machine. The measurements below were taken in the build sandbox (Linux, 2 vCPU). **Windows numbers will differ**, so treat them as an order of magnitude and re-measure with Task Manager.

## Measured resource use

| Process | Memory (RSS) | Notes |
|---|---|---|
| FastAPI backend (uvicorn, 1 worker), idle | ~218 MB | Includes PyMuPDF, Pillow, SQLAlchemy |
| Backend while OCR-ing a page | ~218 MB (no measurable growth) | Pages are processed one at a time |
| Tesseract subprocess, per page | ~43 MB peak | Exits after each page |
| Next.js **production** server (`npm run build && npm start`) | ~227 MB | Recommended on 4 GB |
| Next.js **dev** server (`npm run dev`) after compiling a few pages | ~900 MB total (next-server ~680 MB + node/npm wrappers) | Grows as more routes compile |
| Playwright Chromium (e2e tests) | 300–500 MB | Close other apps; tests run with 1 worker |

| Operation | Time (measured) |
|---|---|
| Digital PDF → extracted, validated invoice | ~0.04 s |
| PNG scan (A4, 170 dpi) → OCR → invoice | ~0.8 s |
| Noisy, skewed JPEG scan → OCR → invoice | ~1.4 s |
| Backend test suite (58 tests) | ~45–50 s |

## Recommended way to run on 4 GB

1. Close browsers and editors you don't need. Windows 11 alone uses 2–2.5 GB.
2. Run the **backend** (≈220 MB) and the **production frontend** (`npm run build` once, then `npm start`, ≈230 MB). Use `npm run dev` only while editing frontend code.
3. Use SQLite locally (no database server) or Supabase remotely. **Do not** install Docker Desktop, PostgreSQL or Redis locally.
4. Keep `AI_PROVIDER=rules`. Upload one document at a time; the upload page already queues files sequentially.
5. Keep `MAX_PDF_PAGES=10` and `OCR_DPI=200`. A higher DPI improves OCR on poor scans but costs memory and time roughly with the square of the DPI.

## Optional local LLM (Ollama + Qwen2.5 0.5B): measured

Measured on 9 Nov 2026 in the build sandbox (Linux, 2 vCPU, no GPU) with Ollama 0.40.15 and `qwen2.5:0.5b-instruct` (Q4_K_M, 398 MB download), `num_ctx=1024`, one request at a time:

| Case | Latency | Result |
|---|---|---|
| Scanned PNG with no invoice number/date printed | 7.6 s | Model added nothing (correct: nothing to find, nothing invented) |
| Noisy JPEG scan | 13.0 s | Model returned non-JSON → **automatic fallback** to rules, noted on the invoice |
| Non-standard layout ("Doc Ref", "Issued", "Pay by", "Seller GST Reg") | 6.4 s | Filled invoice number, invoice date, due date and supplier GSTIN, all verified verbatim in the text |
| Non-standard layout ("Reference number … dated 3rd November 2026") | 3.7 s | Filled the invoice number |

**Peak memory of the Ollama process with the model loaded: ≈ 841 MB.**

What this means on a 4 GB Windows laptop: Windows (≈2–2.5 GB) + backend (≈220 MB) + production frontend (≈230 MB) + Ollama (≈840 MB) is ≈3.3–3.8 GB. That leaves almost nothing for a browser, so expect swapping and multi-second pauses. Recommendation: keep `AI_PROVIDER=rules` on 4 GB. Enable Ollama only to demonstrate the feature, with the dev server and other apps closed, or on an 8 GB+ machine. The app never depends on it: timeouts, bad JSON, missing model or out-of-memory all fall back to rules.

```powershell
# optional (8 GB+ recommended)
winget install Ollama.Ollama
ollama pull qwen2.5:0.5b-instruct
# then in .env
AI_PROVIDER=ollama
```

## ClamAV virus scanning: measured

`clamd` (ClamAV 1.5.4, signatures of 8 Nov 2026) used **≈1.03 GB RAM** after loading its signature database, and took about 20 s to start. That is why it is **off by default** (`MALWARE_SCANNER=none`) on 4 GB machines and the free hosted demo. The always-on PDF active-content policy needs no extra memory. On a server with 2 GB+ free RAM, run ClamAV (included in `deployment/docker-compose.yml`) and set `MALWARE_SCANNER=clamav`.

## Known performance limits
- Processing is synchronous: a 10-page scan takes about 10–15 s inside one request. Fine for an MVP, not for batch ingestion (see *Future improvements* in the README).
- Analytics aggregate in Python over one company's invoices. That is comfortable up to tens of thousands of invoices; beyond that, move to SQL views.
- The in-process rate limiter works for a single backend process only.
