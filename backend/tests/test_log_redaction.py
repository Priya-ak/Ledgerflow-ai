"""Secrets must never reach the logs, and pasted whitespace must not break configuration."""
from __future__ import annotations

import io
import logging

import httpx
import pytest

from app.core import logging as lf_logging
from app.core.config import Settings
from app.core.logging import RedactingFormatter, install_redaction, redact

FAKE_SECRET = "sb_secret_TESTONLYabcdefghijkl123456"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.c2lnbmF0dXJlLXRlc3Q"


def test_redacts_the_exact_leak_seen_in_production():
    line = f"httpx.LocalProtocolError: Illegal header value b'Bearer {FAKE_SECRET}\\n'"
    out = redact(line)
    assert "TESTONLY" not in out and "[REDACTED]" in out and "LocalProtocolError" in out


@pytest.mark.parametrize("text", [
    f"apikey: {FAKE_SECRET}",
    f"Authorization: Bearer {FAKE_JWT}",
    f"token={FAKE_JWT}",
    "postgresql://app_user:S3cretPassw0rd@db.example.supabase.co:5432/postgres",
    "SMTP password=hunter2hunter2",
])
def test_redacts_common_secret_shapes(text):
    out = redact(text)
    for leaked in ("TESTONLY", "eyJhbGci", "S3cretPassw0rd", "hunter2"):
        assert leaked not in out


def test_redacts_exact_values_of_configured_secrets(monkeypatch):
    monkeypatch.setattr(lf_logging.settings, "BREVO_API_KEY", "xkeysib-unusual-format-1234567890")
    assert "xkeysib" not in redact("brevo call failed with xkeysib-unusual-format-1234567890 rejected")


def test_normal_log_lines_are_unchanged():
    line = "2026-11-18 INFO ledgerflow.access method=POST path=/api/v1/documents/upload status=201 ms=84 rid=abc user=u1"
    assert redact(line) == line
    assert redact("token_version mismatch for user") == "token_version mismatch for user"


def _handler_with_stream():
    stream = io.StringIO()
    h = logging.StreamHandler(stream)
    h.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
    return h, stream


def test_tracebacks_are_redacted_on_root_and_uvicorn_handlers():
    root_h, root_out = _handler_with_stream()
    uv_h, uv_out = _handler_with_stream()
    root, uv = logging.getLogger(), logging.getLogger("uvicorn")
    root.addHandler(root_h)
    uv.addHandler(uv_h)
    try:
        install_redaction()
        assert isinstance(root_h.formatter, RedactingFormatter) and isinstance(uv_h.formatter, RedactingFormatter)
        try:
            raise httpx.LocalProtocolError(f"Illegal header value b'Bearer {FAKE_SECRET}\\n'")
        except httpx.LocalProtocolError:
            logging.getLogger("ledgerflow.errors").exception("Unhandled error")
            uv.exception("Exception in ASGI application")
    finally:
        root.removeHandler(root_h)
        uv.removeHandler(uv_h)
    for out in (root_out, uv_out):
        text = out.getvalue()
        assert "LocalProtocolError" in text and "TESTONLY" not in text


def test_install_is_idempotent():
    h, _ = _handler_with_stream()
    root = logging.getLogger()
    root.addHandler(h)
    try:
        install_redaction()
        first = h.formatter
        install_redaction()
        assert h.formatter is first
    finally:
        root.removeHandler(h)


@pytest.mark.parametrize("raw", [f"{FAKE_SECRET}\n", f"  {FAKE_SECRET} ", f"{FAKE_SECRET}\r\n"])
def test_settings_trim_pasted_whitespace(raw):
    s = Settings(_env_file=None, SUPABASE_SERVICE_ROLE_KEY=raw, SUPABASE_URL=" https://x.supabase.co/\n")
    assert s.SUPABASE_SERVICE_ROLE_KEY == FAKE_SECRET
    assert s.SUPABASE_URL == "https://x.supabase.co/"


def test_settings_trim_applies_to_environment_variables(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", f"{FAKE_SECRET}\n")
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@h:5432/db\n")
    s = Settings(_env_file=None)
    assert s.SUPABASE_SERVICE_ROLE_KEY == FAKE_SECRET
    assert s.DATABASE_URL == "postgresql://u:p@h:5432/db"
