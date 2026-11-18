"""Document storage abstraction (local filesystem or Supabase Storage).

Storage keys are generated server-side ({company_id}/documents/{uuid}.{ext});
user-supplied filenames are never used in paths, preventing path traversal.
"""
from __future__ import annotations

import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Protocol

import httpx

from app.core.config import settings
from app.core.errors import AppError


class StorageError(AppError):
    """Storage backend failure.

    Clients get a safe 503 message; the internal detail (status code, exception type)
    is kept in ``log_detail`` and written to the server log by the error handler.
    """

    status_code, code = 503, "storage_unavailable"
    PUBLIC_MESSAGE = "Document storage is temporarily unavailable. Please try again in a few minutes."

    def __init__(self, log_detail: str) -> None:
        super().__init__(self.PUBLIC_MESSAGE)
        self.log_detail = log_detail


class Storage(Protocol):
    name: str

    def save(self, key: str, src: Path, content_type: str) -> None: ...
    def delete(self, key: str) -> None: ...
    @contextmanager
    def local_path(self, key: str) -> Iterator[Path]: ...


def build_key(company_id: str, doc_id: str, ext: str) -> str:
    return f"companies/{company_id}/documents/{doc_id}.{ext}"


class LocalStorage:
    name = "local"

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root or settings.LOCAL_STORAGE_PATH).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root not in p.parents:
            raise StorageError("Invalid storage key.")
        return p

    def save(self, key: str, src: Path, content_type: str) -> None:
        dest = self._path(key)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dest)

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    @contextmanager
    def local_path(self, key: str) -> Iterator[Path]:
        p = self._path(key)
        if not p.exists():
            raise StorageError("Stored file not found.")
        yield p


class SupabaseStorage:
    """Supabase Storage via REST using the service-role key (server-side only).

    The bucket must be PRIVATE; files are only served through the authorised
    /documents/{id}/download endpoint.
    """

    name = "supabase"

    def __init__(self) -> None:
        if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_ROLE_KEY):
            raise StorageError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for Supabase storage.")
        self.base = f"{settings.SUPABASE_URL.rstrip('/')}/storage/v1/object/{settings.SUPABASE_STORAGE_BUCKET}"
        self.headers = {"Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
                        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY}

    def save(self, key: str, src: Path, content_type: str) -> None:
        try:
            with src.open("rb") as fh:
                r = httpx.post(f"{self.base}/{key}",
                               headers={**self.headers, "Content-Type": content_type, "x-upsert": "false"},
                               content=fh, timeout=60)
        except httpx.HTTPError as e:  # DNS failure, refused connection, timeout, paused project
            raise StorageError(f"Supabase upload unreachable ({type(e).__name__}).") from e
        if r.status_code >= 300:
            raise StorageError(f"Supabase upload failed ({r.status_code}).")

    def delete(self, key: str) -> None:
        try:
            r = httpx.delete(f"{self.base}/{key}", headers=self.headers, timeout=30)
        except httpx.HTTPError as e:
            raise StorageError(f"Supabase delete unreachable ({type(e).__name__}).") from e
        if r.status_code >= 300 and r.status_code != 404:
            raise StorageError(f"Supabase delete failed ({r.status_code}).")

    @contextmanager
    def local_path(self, key: str) -> Iterator[Path]:
        suffix = Path(key).suffix
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)
            try:
                with httpx.stream("GET", f"{self.base}/{key}", headers=self.headers, timeout=60) as r:
                    if r.status_code >= 300:
                        raise StorageError(f"Supabase download failed ({r.status_code}).")
                    for chunk in r.iter_bytes(64 * 1024):
                        tmp.write(chunk)
            except httpx.HTTPError as e:
                tmp.close()
                tmp_path.unlink(missing_ok=True)
                raise StorageError(f"Supabase download unreachable ({type(e).__name__}).") from e
            except StorageError:
                tmp.close()
                tmp_path.unlink(missing_ok=True)
                raise
        try:
            yield tmp_path
        finally:
            tmp_path.unlink(missing_ok=True)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = SupabaseStorage() if settings.STORAGE_PROVIDER == "supabase" else LocalStorage()
    return _storage


def set_storage(s: Storage | None) -> None:  # used by tests
    global _storage
    _storage = s
