# Backups and restore runbook

LedgerFlow ships its own encrypted backup tool because the Supabase Free plan has **no automatic backups**.

## What is backed up

| Item | How |
|---|---|
| Every database table | Logical export to gzip'd JSON Lines (`db.jsonl.gz`), read in one consistent `REPEATABLE READ` transaction on PostgreSQL |
| Every stored document (original invoices) | Content-addressed by SHA-256: each file is uploaded **once** and reused by later snapshots |
| Metadata | `manifest.json`: row counts per table, schema (Alembic) revision, checksums, document list |

Everything is encrypted client-side with **Fernet** (AES-128-CBC + HMAC-SHA256) using `BACKUP_ENCRYPTION_KEY` before it leaves the machine, so the storage provider never sees plaintext. Tampering or a wrong key is detected (HMAC) and restore refuses.

The format is database-agnostic: a PostgreSQL backup restores into SQLite and vice versa.

## Schedule (GitHub Actions, `.github/workflows/backup.yml`)

| When | Job |
|---|---|
| Daily 02:10 IST | `create --keep 14` → private Supabase bucket `ledgerflow-backups`, then `verify` |
| Weekly, Monday 03:40 IST | **Restore drill**: `verify --deep` (decrypt + checksum every document), restore the latest snapshot into an empty PostgreSQL 16 service container, sanity-check row counts |
| Any time | *Actions → Backups → Run workflow* (optionally with the drill) |

GitHub emails the repository owner when a scheduled run fails. Scheduled workflows in public repositories are paused after 60 days without repository activity; re-enable them from the Actions tab if that happens.

Retention: 14 daily snapshots. `prune` also deletes documents that no remaining snapshot references.

## Keys: keep them safe

- `BACKUP_ENCRYPTION_KEY`: **if you lose it, every backup is unreadable.** Store a copy in a password manager outside GitHub, Render and Supabase.
- Rotate the key by generating a new one (`python -m app.ops.backup keygen`), updating the secret, and taking a fresh backup. Keep the old key until all snapshots made with it have been pruned.

## Commands

```powershell
cd backend
python -m app.ops.backup keygen                         # new Fernet key
python -m app.ops.backup create                         # snapshot to BACKUP_DESTINATION (local|supabase)
python -m app.ops.backup list
python -m app.ops.backup verify --snapshot latest --deep
python -m app.ops.backup prune --keep 14
```

Local (laptop) use: set `BACKUP_DESTINATION=local` and `BACKUP_LOCAL_PATH=D:\ledgerflow-backups` (ideally an external or synced drive), then schedule `python -m app.ops.backup create --keep 14` daily with Windows Task Scheduler.

## Restoring after an incident

1. Provision an **empty** database (new Supabase project, or local PostgreSQL/SQLite) and run `alembic upgrade head` so the schema revision matches the backup's (shown by `verify`).
2. Point `DATABASE_URL` and the storage settings (`STORAGE_PROVIDER`, `SUPABASE_*`) at the new environment, and set `BACKUP_DESTINATION`, `BACKUP_ENCRYPTION_KEY` and the backup bucket credentials.
3. Check the snapshot first: `python -m app.ops.backup verify --snapshot <id> --deep`
4. Restore: `python -m app.ops.backup restore --snapshot <id> --yes`
   - The target must be empty. `--wipe` deliberately replaces all existing data.
   - `--skip-documents` restores only the database (documents can be restored later).
5. Start the API, sign in, and spot-check recent invoices, documents and audit logs.

Recovery point objective (RPO): ≤ 24 h. Recovery time objective (RTO): roughly 15–30 minutes for an MVP-sized dataset, plus provisioning time.

## Limitations

- These are logical snapshots, not point-in-time recovery. Changes made after the last snapshot are lost. Paid Supabase plans add daily physical backups and PITR.
- A restore must target the same schema revision. Migrate first, or restore into an environment checked out at the matching release.
