# Upgrading a running v1 deployment to this package

This package contains the v1 application plus the v2 additions and the fixes found while testing the live deployment.
**Your live site runs v1. Nothing in this package is deployed until you push it.**

## What is new
| Area | Change |
|---|---|
| Password reset and invitations | Email through Brevo (or SMTP). Set `EMAIL_PROVIDER=console` to only log them |
| Two-factor login | TOTP authenticator app + recovery codes; admins can require it for everyone |
| Upload safety | PDF active-content blocking (always on) and optional ClamAV |
| Backups | Encrypted snapshots of the database and documents, with a GitHub Actions schedule and restore drill |
| Fix | A line break or space pasted into a setting (e.g. the Supabase key) is now trimmed instead of breaking every upload |
| Fix | Secret keys and passwords are masked in all logs, including crash tracebacks |
| Fix | A storage outage shows "Document storage is temporarily unavailable" (HTTP 503) instead of "unexpected error" |
| Fix | Review screen: the Supplier and Purchase order dropdowns showed "Not linked" for linked invoices (display only; the data was correct) |

## Verified
- Backend: 111 tests passed, 3 skipped (they need a real ClamAV or Ollama), on SQLite and PostgreSQL 16.
- Browser (Playwright): 11 tests passed on a fresh local database.
- The dropdown test was run against the old code and fails there ("Not linked"), and passes with the fix.

## Not verified
- The v2 features have **not** been run on Render, Vercel or Supabase.
- No real email has been sent through Brevo. ClamAV does not fit a Render free instance (about 1 GB RAM needed).
- The Docker image is built by Render and GitHub Actions, not in the development environment.

## Render settings to add BEFORE deploying (the service refuses to start without the first one)
| Variable | Value |
|---|---|
| `ENCRYPTION_KEY` | **Required.** Generate on your laptop: `pip install cryptography` then `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `TRUSTED_PROXY_HOPS` | `2` (Vercel + Render). Without it every user shares one rate-limit bucket |
| `EMAIL_PROVIDER` | `console` to start (no email is sent), `brevo` later |
| `BREVO_API_KEY`, `EMAIL_FROM` | Only for `brevo`. `EMAIL_FROM` must be a sender verified in Brevo |
| `SEED_DEMO_ON_START` | Keep `false`. `true` adds the demo company to your database |

Paste every secret as a single line with nothing after the last character.

## Order
1. Commit this package to your GitHub repository (replace the old files; never commit a `.env` file). Uploading through the GitHub website drops the "executable" flag from scripts and can add Windows line endings; the Dockerfile handles both (it starts the script with `sh` and strips carriage returns).
2. Add the Render variables above, then let Render redeploy. The container applies database migration `0002` on start.
3. Vercel redeploys the frontend automatically from the same repository.
4. Check `https://<your-site>/api/v1/system/status`, then sign in and upload `01_valid.pdf`.
5. Rollback: redeploy the previous commit on Render and Vercel. Migration `0002` only adds columns with defaults, so v1 keeps working on the upgraded database.

## Known gaps in this package
- `README.md`, `docs/architecture.md`, `docs/deployment.md`, `docs/testing-guide.md` and `docs/project-review.md` still describe v1. `docs/security.md`, `docs/environment.md`, `docs/backups.md` and `docs/hardware-limitations.md` are updated.
- The review dropdowns list the first 100 suppliers and purchase orders.
