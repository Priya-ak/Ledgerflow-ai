# Deployment (free tier)

Target: **Vercel Hobby** (frontend) → **Render Free** (backend, Docker) → **Supabase Free** (PostgreSQL + Storage). Read [free-resource-guide.md](free-resource-guide.md) first. This setup is a portfolio demo, not a production SLA.

> Not executed in this build: no live deployment was created, and the Dockerfiles could not be built in the sandbox (no network inside build containers). Follow the steps and check each one.

## 1. Supabase
1. Create a project (free). Note the database password.
2. **Project Settings → Database → Connection string → URI.** Use the *session pooler* URI as `DATABASE_URL`.
3. **Storage → New bucket** named `ledgerflow-documents`. Leave **Public** off.
4. **Project Settings → API:** copy the Project URL (`SUPABASE_URL`) and the `service_role` key (`SUPABASE_SERVICE_ROLE_KEY`). The service-role key goes only into the backend's environment.
5. Apply the schema from your machine:
   ```powershell
   cd backend
   .venv\Scripts\Activate.ps1
   $env:DATABASE_URL = "<supabase uri>"
   alembic upgrade head
   # optional demo data (uploads the synthetic documents to Supabase Storage)
   $env:STORAGE_PROVIDER = "supabase"; $env:SUPABASE_URL = "https://<ref>.supabase.co"; $env:SUPABASE_SERVICE_ROLE_KEY = "<service role key>"
   python -m app.demo.seed
   ```

## 2. Render (backend)
1. Push the repository to GitHub.
2. **New → Blueprint** and select the repo. Render reads `deployment/render.yaml` (Docker runtime, so Tesseract is installed).
3. Fill in the `sync: false` variables: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, and `FRONTEND_URL` (your Vercel URL). `JWT_SECRET` and `SECRET_KEY` are generated.
4. The container runs `alembic upgrade head` on start and serves one worker. Check `https://<service>.onrender.com/api/v1/health`.
5. Expect about a minute of cold start after 15 idle minutes. Open the health URL before a demo.

## 3. Vercel (frontend)
1. **Add New → Project**, import the repo, and set **Root Directory** to `frontend`.
2. Environment variables: `BACKEND_URL=https://<service>.onrender.com` (server-side only), `NEXT_PUBLIC_DEMO_MODE=true`.
3. Deploy. The Next.js rewrite proxies `/api/v1/*` to Render, so the session cookie is set on your Vercel domain.
4. The Hobby plan is for **non-commercial** use. Move to Pro or another host for client work.

## Pre-deployment checklist
- [ ] `APP_ENV=staging` or `production`, with strong `JWT_SECRET` and `SECRET_KEY`
- [ ] `STORAGE_PROVIDER=supabase` with a private bucket (Render's disk is ephemeral)
- [ ] `alembic upgrade head` applied; `alembic check` clean
- [ ] `FRONTEND_URL` is the exact Vercel origin
- [ ] Demo accounts only in a clearly labelled demo company; change or remove them for client deployments
- [ ] Database backups: Supabase Free has none, so schedule `pg_dump`
- [ ] Health check, logs and an error tracker (Sentry free tier, optional) reviewed
- [ ] Rollback plan: redeploy the previous Render/Vercel build; `alembic downgrade -1` only if the migration is reversible and data-safe

## Other options
- **Single VM / on-premise** (common for Indian SMEs): run both processes behind Caddy or Nginx with HTTPS, PostgreSQL and local storage on a backed-up disk. `deployment/docker-compose.yml` is a starting point on a machine with 8 GB+ of RAM.
