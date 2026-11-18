"""Storage failures (e.g. a paused Supabase project) must surface as a clear 503, not a generic 500."""
from __future__ import annotations

import logging

import httpx
import pytest

from app.models import Document
from app.services import storage as storage_mod
from app.services.storage import StorageError, SupabaseStorage, set_storage
from tests.conftest import doc


@pytest.fixture
def supabase_storage(monkeypatch):
    monkeypatch.setattr(storage_mod.settings, "SUPABASE_URL", "https://example-paused.supabase.co")
    monkeypatch.setattr(storage_mod.settings, "SUPABASE_SERVICE_ROLE_KEY", "test-service-role-key")
    s = SupabaseStorage()
    set_storage(s)
    yield s
    set_storage(None)


def _unreachable(*_a, **_kw):
    raise httpx.ConnectError("Name or service not known")


def test_unreachable_storage_returns_503_and_creates_nothing(org, supabase_storage, monkeypatch, db, caplog):
    monkeypatch.setattr(storage_mod.httpx, "post", _unreachable)
    with caplog.at_level(logging.ERROR, logger="ledgerflow.errors"):
        r = org["acc"].upload(doc("01_valid"))
    assert r.status_code == 503
    err = r.json()["error"]
    assert err["code"] == "storage_unavailable"
    assert "temporarily unavailable" in err["message"]
    # Internal detail is logged server-side, never returned to the client; the key never appears anywhere.
    assert "ConnectError" in caplog.text and "ConnectError" not in r.text
    assert "test-service-role-key" not in caplog.text + r.text
    assert db.query(Document).count() == 0


def test_storage_http_error_status_returns_503(org, supabase_storage, monkeypatch):
    monkeypatch.setattr(storage_mod.httpx, "post", lambda *a, **kw: httpx.Response(544))
    r = org["acc"].upload(doc("01_valid"))
    assert r.status_code == 503 and r.json()["error"]["code"] == "storage_unavailable"


def test_failed_download_removes_temp_file(supabase_storage, monkeypatch, tmp_path):
    created = []
    real_ntf = storage_mod.tempfile.NamedTemporaryFile

    def tracking_ntf(*a, **kw):
        f = real_ntf(*a, dir=tmp_path, **kw)
        created.append(f.name)
        return f

    monkeypatch.setattr(storage_mod.tempfile, "NamedTemporaryFile", tracking_ntf)
    monkeypatch.setattr(storage_mod.httpx, "stream", _unreachable)
    with pytest.raises(StorageError):
        with supabase_storage.local_path("companies/x/documents/y.pdf"):
            pass
    assert created and not any(p for p in tmp_path.iterdir())


# --- end-to-end: the exact production failure (service key pasted with a trailing newline) ---------------------

class _FakeSupabase:
    """Minimal Supabase Storage stand-in that records the headers it receives."""

    def __init__(self):
        import threading
        from http.server import BaseHTTPRequestHandler, HTTPServer

        outer = self
        self.received: list[dict] = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                n = int(self.headers.get("content-length") or 0)
                self.rfile.read(n)
                outer.received.append({"path": self.path, "auth": self.headers.get("authorization"),
                                       "apikey": self.headers.get("apikey")})
                self.send_response(200)
                self.send_header("content-type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"Key":"ok"}')

            def log_message(self, *_a):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def test_key_with_trailing_newline_now_uploads_end_to_end(org, monkeypatch, db):
    from app.core.config import Settings

    fake = _FakeSupabase()
    try:
        monkeypatch.setenv("NO_PROXY", "127.0.0.1")
        monkeypatch.setenv("no_proxy", "127.0.0.1")
        dirty = Settings(_env_file=None, SUPABASE_URL=f"{fake.url}\n", SUPABASE_SERVICE_ROLE_KEY="sb_secret_TESTONLYabcdef123456\n",
                         SUPABASE_STORAGE_BUCKET="ledgerflow-documents")
        monkeypatch.setattr(storage_mod, "settings", dirty)
        set_storage(SupabaseStorage())
        r = org["acc"].upload(doc("01_valid"))
        assert r.status_code == 201, r.text
        assert db.get(Document, r.json()["id"]).storage_provider == "supabase"  # internal detail, not in the API
        got = fake.received[0]
        assert got["path"].startswith("/storage/v1/object/ledgerflow-documents/companies/")
        assert got["auth"] == "Bearer sb_secret_TESTONLYabcdef123456" and got["apikey"] == "sb_secret_TESTONLYabcdef123456"
    finally:
        set_storage(None)
        fake.close()


def test_unfixed_behaviour_is_a_clean_503_not_a_500(org, monkeypatch):
    """Even if a bad header slips through, the user sees a clear 503 and the key is not echoed."""
    from types import SimpleNamespace

    bad = SimpleNamespace(SUPABASE_URL="http://127.0.0.1:9", SUPABASE_SERVICE_ROLE_KEY="sb_secret_TESTONLYabcdef123456\n",
                          SUPABASE_STORAGE_BUCKET="ledgerflow-documents")
    monkeypatch.setattr(storage_mod, "settings", bad)
    try:
        set_storage(SupabaseStorage())
        r = org["acc"].upload(doc("01_valid"))
    finally:
        set_storage(None)
    assert r.status_code == 503 and r.json()["error"]["code"] == "storage_unavailable"
    assert "TESTONLY" not in r.text
