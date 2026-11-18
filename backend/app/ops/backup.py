"""Encrypted, portable backups of the database and stored documents.

    python -m app.ops.backup keygen                    # print a new BACKUP_ENCRYPTION_KEY
    python -m app.ops.backup create [--no-documents]   # snapshot -> BACKUP_DESTINATION
    python -m app.ops.backup list
    python -m app.ops.backup verify [--snapshot ID] [--deep]
    python -m app.ops.backup restore --snapshot ID --yes [--wipe] [--skip-documents]
    python -m app.ops.backup prune [--keep N]

Layout (local folder or private Supabase Storage bucket):
    snapshots/<UTC timestamp>/manifest.json.enc   row counts, checksums, schema revision
    snapshots/<UTC timestamp>/db.jsonl.gz.enc      every table, one JSON object per row
    documents/<sha256>.enc                          each original file, stored once (deduplicated)

Everything is encrypted with Fernet (AES-128-CBC + HMAC-SHA256) using
BACKUP_ENCRYPTION_KEY. Without that key the backups cannot be read, so keep a
copy of it outside the systems being backed up (password manager / vault).

The format is database-agnostic: a PostgreSQL backup restores into SQLite and
vice versa (into a migrated, empty database). It complements, not replaces,
provider-level point-in-time recovery.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import logging
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator, Protocol

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Boolean, Date, Integer, Numeric, String, func, inspect, select, text
from sqlalchemy.engine import Engine

import app.models  # noqa: F401  (register tables)
from app.core.config import settings
from app.core.database import Base, Money, engine as default_engine
from app.models.base import UTCDateTime
from app.services.storage import get_storage

log = logging.getLogger("ledgerflow.backup")
FORMAT_VERSION = 1


class BackupError(RuntimeError):
    pass


# --------------------------------------------------------------------------- destinations
class Destination(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def list(self, prefix: str) -> list[str]: ...
    def delete(self, keys: list[str]) -> None: ...


class LocalDestination:
    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _p(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise BackupError("Invalid backup key")
        return p

    def put(self, key: str, data: bytes) -> None:
        p = self._p(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".part")
        tmp.write_bytes(data)
        tmp.replace(p)

    def get(self, key: str) -> bytes:
        return self._p(key).read_bytes()

    def list(self, prefix: str) -> list[str]:
        base = self._p(prefix) if prefix else self.root
        if not base.exists():
            return []
        return sorted(str(p.relative_to(self.root)).replace("\\", "/") for p in base.rglob("*") if p.is_file()
                      and not p.name.endswith(".part"))

    def delete(self, keys: list[str]) -> None:
        for k in keys:
            self._p(k).unlink(missing_ok=True)


class SupabaseDestination:
    """Private Supabase Storage bucket, accessed server-side with the service-role key."""

    def __init__(self, bucket: str):
        if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
            raise BackupError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for Supabase backups.")
        self.base = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1"
        self.bucket = bucket
        self.h = {"Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}", "apikey": settings.SUPABASE_SERVICE_ROLE_KEY}
        self.client = httpx.Client(timeout=120, headers=self.h)
        r = self.client.get(f"{self.base}/bucket/{bucket}")
        if r.status_code in (400, 404):
            r = self.client.post(f"{self.base}/bucket", json={"id": bucket, "name": bucket, "public": False})
            if r.status_code >= 300 and "already exists" not in r.text:
                raise BackupError(f"Could not create backup bucket ({r.status_code}).")
        elif r.status_code >= 300:
            raise BackupError(f"Backup bucket check failed ({r.status_code}).")
        elif r.json().get("public"):
            raise BackupError(f"Backup bucket '{bucket}' is PUBLIC. Make it private before storing backups.")

    def put(self, key: str, data: bytes) -> None:
        r = self.client.post(f"{self.base}/object/{self.bucket}/{key}", content=data,
                             headers={"Content-Type": "application/octet-stream", "x-upsert": "true"})
        if r.status_code >= 300:
            raise BackupError(f"Upload of {key} failed ({r.status_code}).")

    def get(self, key: str) -> bytes:
        r = self.client.get(f"{self.base}/object/{self.bucket}/{key}")
        if r.status_code >= 300:
            raise BackupError(f"Download of {key} failed ({r.status_code}).")
        return r.content

    def list(self, prefix: str) -> list[str]:
        out: list[str] = []

        def walk(p: str) -> None:
            offset = 0
            while True:
                r = self.client.post(f"{self.base}/object/list/{self.bucket}",
                                     json={"prefix": p, "limit": 1000, "offset": offset, "sortBy": {"column": "name", "order": "asc"}})
                if r.status_code >= 300:
                    raise BackupError(f"Listing {p} failed ({r.status_code}).")
                items = r.json()
                for it in items:
                    full = f"{p.rstrip('/')}/{it['name']}" if p else it["name"]
                    if it.get("id") is None:  # folder
                        walk(full)
                    else:
                        out.append(full)
                if len(items) < 1000:
                    break
                offset += 1000

        walk(prefix.rstrip("/"))
        return sorted(out)

    def delete(self, keys: list[str]) -> None:
        for i in range(0, len(keys), 500):
            r = self.client.request("DELETE", f"{self.base}/object/{self.bucket}", json={"prefixes": keys[i:i + 500]})
            if r.status_code >= 300:
                raise BackupError(f"Delete failed ({r.status_code}).")


def destination() -> Destination:
    if settings.BACKUP_DESTINATION == "supabase":
        return SupabaseDestination(settings.BACKUP_BUCKET)
    return LocalDestination(settings.BACKUP_LOCAL_PATH)


# --------------------------------------------------------------------------- crypto + codec
def _fernet() -> Fernet:
    if not settings.BACKUP_ENCRYPTION_KEY:
        raise BackupError("BACKUP_ENCRYPTION_KEY is not set. Generate one with: python -m app.ops.backup keygen")
    try:
        return Fernet(settings.BACKUP_ENCRYPTION_KEY.encode())
    except ValueError as e:
        raise BackupError("BACKUP_ENCRYPTION_KEY is not a valid Fernet key.") from e


def _decrypt(f: Fernet, blob: bytes, what: str) -> bytes:
    try:
        return f.decrypt(blob)
    except InvalidToken as e:
        raise BackupError(f"Cannot decrypt {what}: wrong BACKUP_ENCRYPTION_KEY or corrupted file.") from e


def _encode(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _decode(col, v):
    if v is None:
        return None
    t = col.type
    if isinstance(t, (Money, Numeric)):
        return Decimal(v)
    if isinstance(t, UTCDateTime) or t.__class__.__name__ == "DateTime":
        return datetime.fromisoformat(v)
    if isinstance(t, Date):
        return date.fromisoformat(v)
    if isinstance(t, Boolean):
        return bool(v)
    if isinstance(t, Integer):
        return int(v)
    return v


def _schema_revision(eng: Engine) -> str | None:
    if not inspect(eng).has_table("alembic_version"):
        return None
    with eng.connect() as c:
        return c.execute(text("SELECT version_num FROM alembic_version")).scalar()


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# --------------------------------------------------------------------------- operations
@dataclass
class Snapshot:
    id: str
    manifest: dict


def create(dest: Destination | None = None, eng: Engine | None = None, include_documents: bool = True) -> Snapshot:
    dest, eng, f = dest or destination(), eng or default_engine, _fernet()
    now = datetime.now(timezone.utc)
    snap_id = now.strftime("%Y%m%dT%H%M%S") + f"{now.microsecond // 1000:03d}Z"
    if snap_id in set(list_snapshots(dest)):
        raise BackupError(f"Snapshot {snap_id} already exists; retry.")
    counts: dict[str, int] = {}
    raw = io.BytesIO()
    docs: list[dict] = []
    with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz, eng.connect() as conn:
        # REPEATABLE READ gives one consistent view across all tables on PostgreSQL.
        if eng.dialect.name == "postgresql":
            conn.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
        for table in Base.metadata.sorted_tables:
            n = 0
            for row in conn.execute(select(table)).mappings():
                gz.write((json.dumps({"t": table.name, "r": {k: _encode(v) for k, v in row.items()}},
                                     separators=(",", ":"), ensure_ascii=False) + "\n").encode())
                n += 1
                if table.name == "documents":
                    docs.append({"sha256": row["sha256"], "storage_key": row["storage_key"], "size": row["size_bytes"]})
            counts[table.name] = n
    db_bytes = raw.getvalue()

    uploaded = 0
    if include_documents and docs:
        existing = set(dest.list("documents"))
        storage = get_storage()
        for d in {d["sha256"]: d for d in docs}.values():
            key = f"documents/{d['sha256']}.enc"
            if key in existing:
                continue  # content-addressed: unchanged files are never re-uploaded
            with storage.local_path(d["storage_key"]) as p:
                data = p.read_bytes()
            if _sha(data) != d["sha256"]:
                raise BackupError(f"Stored file {d['storage_key']} does not match its recorded checksum.")
            dest.put(key, f.encrypt(data))
            uploaded += 1

    manifest = {
        "format": FORMAT_VERSION, "snapshot": snap_id, "created_at": datetime.now(timezone.utc).isoformat(),
        "dialect": eng.dialect.name, "schema_revision": _schema_revision(eng), "tables": counts,
        "db_sha256": _sha(db_bytes), "db_bytes": len(db_bytes), "documents_included": include_documents,
        "documents": docs if include_documents else [], "documents_uploaded": uploaded,
    }
    dest.put(f"snapshots/{snap_id}/db.jsonl.gz.enc", f.encrypt(db_bytes))
    dest.put(f"snapshots/{snap_id}/manifest.json.enc", f.encrypt(json.dumps(manifest).encode()))  # written last = commit marker
    return Snapshot(snap_id, manifest)


def list_snapshots(dest: Destination | None = None) -> list[str]:
    dest = dest or destination()
    return sorted({k.split("/")[1] for k in dest.list("snapshots") if k.endswith("manifest.json.enc")})


def _resolve(dest: Destination, snapshot: str | None) -> str:
    snaps = list_snapshots(dest)
    if not snaps:
        raise BackupError("No snapshots found.")
    if snapshot in (None, "latest"):
        return snaps[-1]
    if snapshot not in snaps:
        raise BackupError(f"Snapshot {snapshot} not found.")
    return snapshot


def _load(dest: Destination, snap: str) -> tuple[dict, list[dict]]:
    f = _fernet()
    manifest = json.loads(_decrypt(f, dest.get(f"snapshots/{snap}/manifest.json.enc"), "manifest"))
    db_bytes = _decrypt(f, dest.get(f"snapshots/{snap}/db.jsonl.gz.enc"), "database dump")
    if _sha(db_bytes) != manifest["db_sha256"]:
        raise BackupError("Database dump checksum mismatch: the backup is corrupted.")
    rows = [json.loads(line) for line in gzip.decompress(db_bytes).splitlines() if line]
    return manifest, rows


def verify(dest: Destination | None = None, snapshot: str | None = None, deep: bool = False) -> dict:
    dest = dest or destination()
    snap = _resolve(dest, snapshot)
    manifest, rows = _load(dest, snap)
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["t"]] = counts.get(r["t"], 0) + 1
    problems = [f"{t}: manifest {n} rows, dump {counts.get(t, 0)}" for t, n in manifest["tables"].items() if counts.get(t, 0) != n]
    existing = set(dest.list("documents"))
    missing = [d["sha256"] for d in manifest["documents"] if f"documents/{d['sha256']}.enc" not in existing]
    if missing:
        problems.append(f"{len(missing)} document(s) missing from the backup store")
    if deep:
        f = _fernet()
        for d in manifest["documents"]:
            key = f"documents/{d['sha256']}.enc"
            if key in existing and _sha(_decrypt(f, dest.get(key), key)) != d["sha256"]:
                problems.append(f"document {d['sha256'][:12]} checksum mismatch")
    return {"snapshot": snap, "ok": not problems, "problems": problems, "rows": sum(counts.values()),
            "documents": len(manifest["documents"]), "schema_revision": manifest.get("schema_revision")}


def restore(dest: Destination | None = None, snapshot: str | None = None, eng: Engine | None = None,
            wipe: bool = False, restore_documents: bool = True) -> dict:
    dest, eng = dest or destination(), eng or default_engine
    snap = _resolve(dest, snapshot)
    manifest, rows = _load(dest, snap)
    current_rev = _schema_revision(eng)
    if manifest.get("schema_revision") and current_rev and manifest["schema_revision"] != current_rev:
        raise BackupError(f"Schema mismatch: backup is at {manifest['schema_revision']}, database at {current_rev}. "
                          "Migrate the target to the same revision first.")
    tables = {t.name: t for t in Base.metadata.sorted_tables}
    by_table: dict[str, list[dict]] = {}
    for r in rows:
        by_table.setdefault(r["t"], []).append(r["r"])
    with eng.begin() as conn:
        populated = conn.execute(select(func.count()).select_from(tables["companies"])).scalar()
        if populated and not wipe:
            raise BackupError("Target database is not empty. Use --wipe to replace ALL its data.")
        if wipe:
            if eng.dialect.name == "postgresql":
                conn.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " CASCADE"))
            else:
                for t in reversed(Base.metadata.sorted_tables):
                    conn.execute(t.delete())
        for name, table in tables.items():
            data = by_table.get(name, [])
            cols = {c.name: c for c in table.columns}
            for i in range(0, len(data), 500):
                conn.execute(table.insert(), [{k: _decode(cols[k], v) for k, v in r.items() if k in cols} for r in data[i:i + 500]])
    restored_docs = 0
    if restore_documents and manifest["documents"]:
        f, storage = _fernet(), get_storage()
        import tempfile
        for d in manifest["documents"]:
            data = _decrypt(f, dest.get(f"documents/{d['sha256']}.enc"), d["sha256"])
            if _sha(data) != d["sha256"]:
                raise BackupError(f"Document {d['sha256'][:12]} failed its checksum.")
            with tempfile.NamedTemporaryFile(delete=False) as tmp:
                tmp.write(data)
            try:
                storage.save(d["storage_key"], Path(tmp.name), "application/octet-stream")
            finally:
                Path(tmp.name).unlink(missing_ok=True)
            restored_docs += 1
    return {"snapshot": snap, "rows": len(rows), "tables": len(by_table), "documents": restored_docs}


def prune(dest: Destination | None = None, keep: int | None = None) -> dict:
    dest, keep = dest or destination(), keep or settings.BACKUP_KEEP
    snaps = list_snapshots(dest)
    old = snaps[:-keep] if len(snaps) > keep else []
    for s in old:
        dest.delete([k for k in dest.list(f"snapshots/{s}")])
    # Garbage-collect documents no longer referenced by any remaining snapshot.
    f = _fernet()
    referenced: set[str] = set()
    for s in list_snapshots(dest):
        m = json.loads(_decrypt(f, dest.get(f"snapshots/{s}/manifest.json.enc"), "manifest"))
        referenced |= {f"documents/{d['sha256']}.enc" for d in m["documents"]}
    orphans = [k for k in dest.list("documents") if k not in referenced]
    if orphans:
        dest.delete(orphans)
    return {"deleted_snapshots": old, "kept": min(len(snaps), keep), "deleted_documents": len(orphans)}


# --------------------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level="INFO", format="%(levelname)s %(message)s")
    ap = argparse.ArgumentParser(prog="python -m app.ops.backup", description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("keygen")
    c = sub.add_parser("create")
    c.add_argument("--no-documents", action="store_true")
    c.add_argument("--keep", type=int, help="prune to this many snapshots afterwards")
    sub.add_parser("list")
    v = sub.add_parser("verify")
    v.add_argument("--snapshot", default="latest")
    v.add_argument("--deep", action="store_true", help="decrypt and checksum every document")
    r = sub.add_parser("restore")
    r.add_argument("--snapshot", required=True)
    r.add_argument("--yes", action="store_true")
    r.add_argument("--wipe", action="store_true")
    r.add_argument("--skip-documents", action="store_true")
    p = sub.add_parser("prune")
    p.add_argument("--keep", type=int)
    a = ap.parse_args(argv)
    try:
        if a.cmd == "keygen":
            print(Fernet.generate_key().decode())
            return 0
        if a.cmd == "create":
            snap = create(include_documents=not a.no_documents)
            out = {"snapshot": snap.id, "rows": sum(snap.manifest["tables"].values()),
                   "documents": len(snap.manifest["documents"]), "documents_uploaded": snap.manifest["documents_uploaded"]}
            if a.keep:
                out["prune"] = prune(keep=a.keep)
            print(json.dumps(out))
            return 0
        if a.cmd == "list":
            print("\n".join(list_snapshots()))
            return 0
        if a.cmd == "verify":
            res = verify(snapshot=a.snapshot, deep=a.deep)
            print(json.dumps(res))
            return 0 if res["ok"] else 2
        if a.cmd == "restore":
            if not a.yes:
                print("Refusing to restore without --yes.", file=sys.stderr)
                return 1
            print(json.dumps(restore(snapshot=a.snapshot, wipe=a.wipe, restore_documents=not a.skip_documents)))
            return 0
        if a.cmd == "prune":
            print(json.dumps(prune(keep=a.keep)))
            return 0
    except BackupError as e:
        log.error("%s", e)
        return 1
    return 1


if __name__ == "__main__":
    sys.exit(main())
