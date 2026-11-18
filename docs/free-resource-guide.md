# Free-resource guide

LedgerFlow AI can be built, run and tested at **₹0**. Every hosted service below is optional. The complete application runs locally with SQLite, local file storage and Tesseract.

> Free tiers change. The figures below were read from each provider's official page on **9 November 2026**. Check them again before relying on them.

## What the project uses

| Need | Free choice | Required? |
|---|---|---|
| Backend runtime | Python 3.11–3.13, FastAPI, Uvicorn | Yes |
| Frontend runtime | Node.js 20/22, Next.js 15 | Yes |
| Database | SQLite (local) or Supabase Free PostgreSQL | One of them |
| Document storage | Local disk or Supabase Storage (free) | One of them |
| PDF text | PyMuPDF | Yes |
| OCR | Tesseract (UB Mannheim Windows build) | Recommended; digital PDFs work without it |
| AI | Rules (built in) · Ollama + Qwen2.5 0.5B (local) · Gemini free tier | No |
| Reports | openpyxl | Yes |
| Source control | GitHub Free | Optional |
| Frontend hosting | Vercel Hobby | Optional |
| Backend hosting | Render Free (Docker) | Optional |

Nothing in the code calls a paid API, and nothing enables billing.

## Provider limits that affect LedgerFlow

### Supabase Free ([pricing](https://supabase.com/pricing))
- 500 MB database per project, 1 GB file storage, 50 MB max upload size, 5 GB egress, 50,000 monthly active users, and 2 active projects.
- **Free projects are paused after 1 week of inactivity.** Open the dashboard or restore the project before a demo.
- **No automatic backups on Free.** Run `pg_dump` yourself before important demos.
- LedgerFlow fit: about 2–5 KB of rows per invoice plus the file. 1 GB of storage holds roughly 3,000–10,000 typical invoice PDFs. Keep `MAX_UPLOAD_MB` ≤ 50.

### Render Free ([docs](https://render.com/docs/free))
- A free web service **spins down after 15 minutes without traffic**, and the next request takes **about a minute** to wake it up.
- 750 free instance hours per workspace per month.
- **The filesystem is ephemeral:** files are lost on redeploy, restart or spin-down. You **must** use `STORAGE_PROVIDER=supabase` and a Supabase `DATABASE_URL` on Render.
- Free Render Postgres **expires 30 days after creation**. Use Supabase Postgres instead.
- Instance RAM and CPU are small. The backend idles at about 220 MB RSS (measured locally). Keep `AI_PROVIDER=rules` on Render; do not run Ollama there.

### Vercel Hobby ([docs](https://vercel.com/docs/plans/hobby))
- **Personal, non-commercial use only.** A paying client deployment needs Vercel Pro or another host.
- Includes 1,000,000 function invocations, 100 GB Fast Data Transfer and a 300 s maximum function duration per month.
- LedgerFlow's frontend is mostly static pages plus a proxy rewrite, so it uses very little of this.

### Gemini API free tier (optional)
- Quotas and data-use terms differ between free and paid tiers and change often. Check Google's current terms before use.
- LedgerFlow sends document text to Gemini **only** when `AI_PROVIDER=gemini`, `GEMINI_API_KEY` is set **and** `ALLOW_CLOUD_AI=true`. Use synthetic documents only. Never send real supplier or bank data to a free-tier API.

### Ollama (optional, local)
- Free and offline. `qwen2.5:0.5b-instruct` is about a 400 MB download. See [hardware-limitations.md](hardware-limitations.md) before enabling it on 4 GB of RAM.

## What is *not* free (and not required)
- Custom domain: optional. Vercel and Render subdomains work.
- Transactional email (password-reset delivery): not configured. In development the reset link is shown on screen; in production, an email provider (or Supabase Auth) must be integrated.
- Backups, uptime SLAs and commercial hosting: required for a real client deployment, and budgeted in [project-review.md](project-review.md).

**Do not treat trial credits as permanent free resources**, and do not describe a free-tier deployment as production-ready.
