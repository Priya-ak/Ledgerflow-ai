import re
import socket
import time

import httpx
import pytest

from app.models import EmailLog
from app.services import email as email_svc
from tests.conftest import PASSWORD, add_user, doc, register


@pytest.fixture
def outbox(monkeypatch):
    """Capture every email the app sends through the configured provider."""
    sent = []
    monkeypatch.setattr(email_svc.settings, "EMAIL_PROVIDER", "console")
    monkeypatch.setitem(email_svc.PROVIDERS, "console", lambda m: sent.append(m) or f"<msg-{len(sent)}@test>")
    return sent


def _link_token(msg) -> str:
    return re.search(r"reset-password\?token=([A-Za-z0-9_\-%]+)", msg.text).group(1)


def test_forgot_password_sends_email_and_hides_token_when_email_is_configured(client, outbox, monkeypatch, db):
    register(client, "Co", "a@co.example")
    monkeypatch.setattr(email_svc.settings, "EMAIL_PROVIDER", "brevo")
    monkeypatch.setitem(email_svc.PROVIDERS, "brevo", lambda m: outbox.append(m) or "brevo-id-1")
    r = client.post("/api/v1/auth/forgot-password", json={"email": "a@co.example"})
    assert r.status_code == 200 and r.json()["dev_reset_token"] is None  # never exposed when real email is used
    assert len(outbox) == 1 and outbox[0].template == "password_reset"
    token = _link_token(outbox[0])
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Brandnew12345"}).status_code == 200
    log = db.query(EmailLog).filter_by(template="password_reset").one()
    assert log.status == "sent" and log.provider_message_id == "brevo-id-1"
    assert token not in (log.subject + (log.error or ""))  # bodies/tokens are not stored


def test_unknown_email_sends_nothing(client, outbox):
    r = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@co.example"})
    assert r.status_code == 200 and outbox == []


def test_invitation_flow(client, outbox):
    admin = register(client, "Co", "boss@co.example")
    r = admin.post("/users", json={"email": "new@co.example", "full_name": "New Person", "role": "accountant", "send_invite": True})
    assert r.status_code == 201
    invite = next(m for m in outbox if m.template == "user_invite")
    assert "Set your password" in invite.html and invite.to == "new@co.example"
    token = _link_token(invite)
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "Welcome12345"}).status_code == 200
    assert client.post("/api/v1/auth/login", json={"email": "new@co.example", "password": "Welcome12345"}).status_code == 200


def test_create_user_requires_password_or_invite(client):
    admin = register(client, "Co", "boss@co.example")
    r = admin.post("/users", json={"email": "x@co.example", "full_name": "Xx", "role": "approver"})
    assert r.status_code == 422


def test_approval_notifications(org, outbox):
    acc, appr = org["acc"], org["appr"]
    d = acc.upload(doc("07_extra_items")).json()
    inv = acc.post("/invoices/extract", json={"document_id": d["id"]}).json()
    outbox.clear()
    acc.post(f"/invoices/{inv['id']}/submit", json={"note": "please"})
    to_approver = [m for m in outbox if m.template == "approval_requested"]
    assert [m.to for m in to_approver] == ["appr@acme-test.example"]
    assert f"/app/invoices/{inv['id']}" in to_approver[0].text and "KST/26-27/0457" in to_approver[0].subject
    outbox.clear()
    appr.post(f"/invoices/{inv['id']}/reject", json={"reason": "Pallets were not ordered"})
    decided = [m for m in outbox if m.template == "invoice_rejected"]
    assert decided and decided[0].to == "acc@acme-test.example" and "Pallets were not ordered" in decided[0].text


def test_approval_notifications_can_be_disabled(org, outbox):
    org["admin"].put("/company/settings", json={"currency": "INR", "amount_tolerance": "1.00", "po_price_tolerance_pct": "2.00",
                                               "po_qty_tolerance_pct": "0.00", "duplicate_window_days": 90, "notify_approvers": False})
    acc = org["acc"]
    inv = acc.post("/invoices/extract", json={"document_id": acc.upload(doc("07_extra_items")).json()["id"]}).json()
    outbox.clear()
    acc.post(f"/invoices/{inv['id']}/submit", json={})
    assert not [m for m in outbox if m.template == "approval_requested"]


def test_brevo_provider_payload_and_errors(monkeypatch):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append((url, json, headers))
        return httpx.Response(201, json={"messageId": "<abc@smtp-relay.mailin.fr>"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(email_svc.settings, "BREVO_API_KEY", "xkeysib-test")
    monkeypatch.setattr(email_svc.settings, "EMAIL_FROM", "sender@example.com")
    monkeypatch.setattr(email_svc.httpx, "post", fake_post)
    msg = email_svc.security_notice_email("u@example.com", "U", event="test", company_id=None, user_id=None)
    assert email_svc._send_brevo(msg) == "<abc@smtp-relay.mailin.fr>"
    url, body, headers = calls[0]
    assert url == email_svc.BREVO_URL and headers["api-key"] == "xkeysib-test"
    assert body["sender"]["email"] == "sender@example.com" and body["to"][0]["email"] == "u@example.com"
    assert body["htmlContent"] and body["textContent"]

    monkeypatch.setattr(email_svc.httpx, "post", lambda *a, **k: httpx.Response(401, json={"code": "unauthorized"}, request=httpx.Request("POST", "x")))
    with pytest.raises(email_svc.EmailError) as e:
        email_svc._send_brevo(msg)
    assert not e.value.transient and "unauthorized" in str(e.value)


def test_transient_failures_retry_then_record(monkeypatch, db):
    attempts = []

    def flaky(m):
        attempts.append(1)
        if len(attempts) < 3:
            raise email_svc.EmailError("timeout", transient=True)
        return "ok-3"

    monkeypatch.setattr(email_svc.settings, "EMAIL_PROVIDER", "console")
    monkeypatch.setitem(email_svc.PROVIDERS, "console", flaky)
    monkeypatch.setattr(email_svc.time, "sleep", lambda s: None)
    entry = email_svc.deliver(email_svc.security_notice_email("u@example.com", "U", event="x", company_id=None, user_id=None))
    assert len(attempts) == 3 and entry.status == "sent"

    monkeypatch.setitem(email_svc.PROVIDERS, "console", lambda m: (_ for _ in ()).throw(email_svc.EmailError("bad address")))
    entry = email_svc.deliver(email_svc.security_notice_email("u@example.com", "U", event="x", company_id=None, user_id=None))
    assert entry.status == "failed" and "bad address" in entry.error


def test_smtp_provider_against_real_smtp_server(monkeypatch):
    """Speaks real SMTP to a local aiosmtpd server (no network needed)."""
    from aiosmtpd.controller import Controller

    received = []

    class Handler:
        async def handle_DATA(self, server, session, envelope):
            received.append(envelope)
            return "250 OK"

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    ctl = Controller(Handler(), hostname="127.0.0.1", port=port)
    ctl.start()
    try:
        for k, v in {"SMTP_HOST": "127.0.0.1", "SMTP_PORT": port, "SMTP_SECURITY": "none", "SMTP_USERNAME": "",
                     "EMAIL_FROM": "noreply@ledgerflow.example"}.items():
            monkeypatch.setattr(email_svc.settings, k, v)
        msg = email_svc.password_reset_email("dest@example.com", "Dee", "tok123", invite=False, company_id=None, user_id=None)
        mid = email_svc._send_smtp(msg)
        for _ in range(50):
            if received:
                break
            time.sleep(0.05)
        assert mid and received[0].rcpt_tos == ["dest@example.com"]
        body = received[0].content.decode()
        assert "Reset your LedgerFlow AI password" in body and "multipart/alternative" in body
    finally:
        ctl.stop()


def test_console_provider_redacts_bodies_outside_development(monkeypatch, caplog):
    monkeypatch.setattr(email_svc.settings, "APP_ENV", "production")
    msg = email_svc.password_reset_email("x@example.com", "X", "SECRET-TOKEN-123", invite=False, company_id=None, user_id=None)
    with caplog.at_level("INFO", logger="ledgerflow.email"):
        email_svc._send_console(msg)
    assert "SECRET-TOKEN-123" not in caplog.text
