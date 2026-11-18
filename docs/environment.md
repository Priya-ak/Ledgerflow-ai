# Environment variables

The backend reads `.env` in the repository root (or `backend/.env`). The frontend reads `frontend/.env.local`. Templates: [`.env.example`](../.env.example) and [`frontend/.env.example`](../frontend/.env.example).

## Backend (server-side only)

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `APP_ENV` | no | `development` | `staging`/`production` require strong secrets and force Secure cookies |
| `DATABASE_URL` | no | SQLite file | PostgreSQL/Supabase URI (`postgres://` is normalised) |
| `JWT_SECRET` | **prod** | random per process in dev | Signs session tokens (≥32 chars) |
| `SECRET_KEY` | **prod** | random per process in dev | HMAC key for password-reset tokens |
| `JWT_EXPIRE_MINUTES` | no | `480` | Session lifetime |
| `STORAGE_PROVIDER` | no | `local` | `local` or `supabase` |
| `LOCAL_STORAGE_PATH` | no | `backend/storage` | Local document folder |
| `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_STORAGE_BUCKET` | for `supabase` storage | — | Private bucket access. **Service-role key is a secret** |
| `SUPABASE_ANON_KEY` | no | — | Reserved for a future Supabase Auth integration; unused today |
| `MAX_UPLOAD_MB`, `MAX_PDF_PAGES` | no | `10`, `10` | Upload limits |
| `OCR_ENGINE` | no | `tesseract` | `none` disables OCR (digital PDFs still work) |
| `TESSERACT_CMD` | Windows usually | PATH | e.g. `C:\Program Files\Tesseract-OCR\tesseract.exe` |
| `OCR_DPI` | no | `200` | Render DPI for scanned PDF pages |
| `AI_PROVIDER` | no | `rules` | `rules`, `ollama`, `gemini` |
| `AI_TIMEOUT_SECONDS` | no | `45` | Model call timeout before falling back |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_NUM_CTX` | for ollama | `http://localhost:11434`, `qwen2.5:0.5b-instruct`, `1024` | Local model |
| `GEMINI_API_KEY`, `GEMINI_MODEL` | for gemini | —, `gemini-2.0-flash` | Cloud model. **Key is a secret** |
| `ALLOW_CLOUD_AI` | for gemini | `false` | Must be `true` to send text to Gemini |
| `ENCRYPTION_KEY` | **prod** | derived from `SECRET_KEY` in dev | Fernet key that encrypts 2FA secrets at rest (`python -m app.ops.backup keygen`) |
| `EMAIL_PROVIDER` | no | `console` | `brevo`, `smtp`, `console` (logs; bodies redacted outside dev) or `none` |
| `EMAIL_FROM`, `EMAIL_FROM_NAME` | for brevo/smtp | — , `LedgerFlow AI` | Sender (must be a verified sender in Brevo) |
| `BREVO_API_KEY` | for brevo | — | **Secret.** Brevo transactional API key |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_SECURITY` | for smtp | —, `587`, —, —, `starttls` | Any SMTP server (e.g. Gmail with an app password). **Password is a secret** |
| `APP_PUBLIC_URL` | no | first `FRONTEND_URL` | Base URL used in email links |
| `MFA_ISSUER` | no | `LedgerFlow AI` | Name shown in authenticator apps |
| `MALWARE_SCANNER` | no | `none` | `clamav` to scan every upload with clamd (needs ~1 GB RAM) |
| `CLAMAV_HOST`, `CLAMAV_PORT`, `CLAMAV_TIMEOUT_SECONDS` | for clamav | `127.0.0.1`, `3310`, `30` | clamd TCP endpoint |
| `MALWARE_SCAN_FAIL_CLOSED` | no | `true` | Reject uploads (503) if the scanner is unreachable |
| `TRUSTED_PROXY_HOPS` | hosted | `0` | Reverse proxies in front of the API that append to `X-Forwarded-For` (Vercel → Render = `2`) |
| `SEED_DEMO_ON_START` | no | `false` | Container start seeds the demo company if missing (hosted demo) |
| `BACKUP_ENCRYPTION_KEY` | for backups | — | **Secret.** Fernet key; losing it makes backups unreadable |
| `BACKUP_DESTINATION`, `BACKUP_LOCAL_PATH`, `BACKUP_BUCKET`, `BACKUP_KEEP` | no | `local`, `backend/backups`, `ledgerflow-backups`, `14` | Where and how many snapshots to keep |
| `FRONTEND_URL` | no | `http://localhost:3000` | CORS allow-list (comma-separated) |
| `BACKEND_URL` | no | `http://localhost:8000` | Informational |
| `DEMO_MODE` | no | `true` | Shows the dev reset link in development only |
| `LOG_LEVEL` | no | `INFO` | Python logging level |

## Frontend

| Variable | Exposed to browser | Purpose |
|---|---|---|
| `BACKEND_URL` | **no** (used by the Next.js server rewrite) | Where `/api/v1/*` is proxied |
| `NEXT_PUBLIC_DEMO_MODE` | yes | Shows demo-account buttons on the login page |
| `NEXT_PUBLIC_CONTACT_EMAIL` | yes | Contact form `mailto:` address |

Never put `JWT_SECRET`, `SECRET_KEY`, `ENCRYPTION_KEY`, `BACKUP_ENCRYPTION_KEY`, `BREVO_API_KEY`, `SMTP_PASSWORD`, `SUPABASE_SERVICE_ROLE_KEY`, `GEMINI_API_KEY` or `DATABASE_URL` in any `NEXT_PUBLIC_*` variable or frontend file.
