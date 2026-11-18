"""Outbound email: console (dev) | smtp | brevo (HTTPS API) | none.

Emails are sent after the HTTP response (FastAPI BackgroundTasks) so request
latency and timing do not depend on the provider, and a provider outage never
breaks the user's action. Every attempt is recorded in email_logs WITHOUT the
body, because bodies can contain one-time links.
"""
from __future__ import annotations

import html
import logging
import smtplib
import ssl
import time
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

import httpx

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import EmailLog

log = logging.getLogger("ledgerflow.email")

BREVO_URL = "https://api.brevo.com/v3/smtp/email"


@dataclass
class Email:
    to: str
    subject: str
    text: str
    html: str
    template: str
    to_name: str | None = None
    company_id: str | None = None
    user_id: str | None = None
    tags: list[str] = field(default_factory=list)


class EmailError(RuntimeError):
    def __init__(self, message: str, transient: bool = False):
        super().__init__(message)
        self.transient = transient


# ----------------------------------------------------------------------------- providers
def _send_console(msg: Email) -> str:
    if settings.APP_ENV in ("development", "test"):
        log.info("EMAIL (console) to=%s subject=%s\n%s", msg.to, msg.subject, msg.text)
    else:  # never write links/tokens to production logs
        log.info("EMAIL (console, body redacted) to=%s subject=%s", msg.to, msg.subject)
    return make_msgid(domain="console.ledgerflow")


def _send_smtp(msg: Email) -> str:
    if not settings.SMTP_HOST:
        raise EmailError("SMTP_HOST is not configured.")
    m = EmailMessage()
    m["From"] = formataddr((settings.EMAIL_FROM_NAME, settings.EMAIL_FROM))
    m["To"] = formataddr((msg.to_name or "", msg.to))
    m["Subject"] = msg.subject
    mid = make_msgid(domain=settings.EMAIL_FROM.split("@")[-1])
    m["Message-ID"] = mid
    m.set_content(msg.text)
    m.add_alternative(msg.html, subtype="html")
    try:
        if settings.SMTP_SECURITY == "ssl":
            server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.EMAIL_TIMEOUT_SECONDS,
                                      context=ssl.create_default_context())
        else:
            server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=settings.EMAIL_TIMEOUT_SECONDS)
        with server:
            if settings.SMTP_SECURITY == "starttls":
                server.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME:
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            server.send_message(m)
    except (smtplib.SMTPServerDisconnected, smtplib.SMTPConnectError, TimeoutError, OSError) as e:
        raise EmailError(f"SMTP connection failed: {type(e).__name__}", transient=True) from e
    except smtplib.SMTPException as e:
        raise EmailError(f"SMTP rejected the message: {type(e).__name__}") from e
    return mid


def _send_brevo(msg: Email) -> str:
    if not settings.BREVO_API_KEY:
        raise EmailError("BREVO_API_KEY is not configured.")
    payload = {
        "sender": {"name": settings.EMAIL_FROM_NAME, "email": settings.EMAIL_FROM},
        "to": [{"email": msg.to, **({"name": msg.to_name} if msg.to_name else {})}],
        "subject": msg.subject, "htmlContent": msg.html, "textContent": msg.text,
        "tags": msg.tags or [msg.template],
    }
    try:
        r = httpx.post(BREVO_URL, json=payload, timeout=settings.EMAIL_TIMEOUT_SECONDS,
                       headers={"api-key": settings.BREVO_API_KEY, "accept": "application/json"})
    except httpx.HTTPError as e:
        raise EmailError(f"Brevo unreachable: {type(e).__name__}", transient=True) from e
    if r.status_code in (429,) or r.status_code >= 500:
        raise EmailError(f"Brevo temporary error {r.status_code}", transient=True)
    if r.status_code >= 300:
        # 400/401/403 carry a JSON code like "unauthorized" or "invalid_parameter"; never the key.
        detail = r.json().get("code", "") if r.headers.get("content-type", "").startswith("application/json") else ""
        raise EmailError(f"Brevo rejected the message ({r.status_code} {detail})".strip())
    return str(r.json().get("messageId", ""))


PROVIDERS = {"console": _send_console, "smtp": _send_smtp, "brevo": _send_brevo}


def deliver(msg: Email) -> EmailLog:
    """Send with up to 3 attempts on transient failures, then record the outcome."""
    provider = settings.EMAIL_PROVIDER
    status, mid, error = "skipped", None, None
    if provider != "none":
        fn = PROVIDERS[provider]
        for attempt in range(3):
            try:
                mid, status, error = fn(msg), "sent", None
                break
            except EmailError as e:
                status, error = "failed", str(e)
                if not e.transient or attempt == 2:
                    break
                time.sleep(0.5 * 2 ** attempt)
    if status == "failed":
        log.error("email_failed template=%s to=%s error=%s", msg.template, msg.to, error)
    else:
        log.info("email_%s template=%s to=%s provider=%s", status, msg.template, msg.to, provider)
    db = SessionLocal()
    try:
        entry = EmailLog(company_id=msg.company_id, user_id=msg.user_id, to_email=msg.to, template=msg.template,
                         subject=msg.subject[:255], provider=provider, status=status, provider_message_id=mid,
                         error=(error or "")[:1000] or None)
        db.add(entry)
        db.commit()
        return entry
    finally:
        db.close()


# ----------------------------------------------------------------------------- templates
def _layout(title: str, intro: str, button: tuple[str, str] | None, rows: list[tuple[str, str]] | None = None,
            footer: str = "") -> str:
    e = html.escape
    table = ""
    if rows:
        table = "<table style='width:100%;border-collapse:collapse;margin:16px 0;font-size:14px'>" + "".join(
            f"<tr><td style='padding:6px 0;color:#5b6779'>{e(k)}</td><td style='padding:6px 0;text-align:right;"
            f"font-weight:600'>{e(v)}</td></tr>" for k, v in rows) + "</table>"
    btn = ""
    if button:
        btn = (f"<p style='margin:24px 0'><a href='{e(button[1])}' style='background:#0e5767;color:#fff;"
               f"padding:10px 18px;border-radius:8px;text-decoration:none;font-weight:600'>{e(button[0])}</a></p>"
               f"<p style='font-size:12px;color:#5b6779'>Or paste this link into your browser:<br>{e(button[1])}</p>")
    return (f"<!doctype html><html><body style='margin:0;background:#f6f7f9;font-family:Segoe UI,Arial,sans-serif;"
            f"color:#0f172a'><div style='max-width:560px;margin:0 auto;padding:24px'>"
            f"<p style='font-weight:700;color:#0e5767;margin:0 0 16px'>LedgerFlow AI</p>"
            f"<div style='background:#fff;border:1px solid #e2e7ee;border-radius:12px;padding:24px'>"
            f"<h1 style='font-size:18px;margin:0 0 12px'>{e(title)}</h1><p style='font-size:14px;line-height:1.6'>"
            f"{e(intro)}</p>{table}{btn}</div><p style='font-size:12px;color:#5b6779;margin-top:16px'>{e(footer)}"
            f"</p></div></body></html>")


def password_reset_email(to: str, name: str, token: str, *, invite: bool, company_id: str, user_id: str,
                         company_name: str = "") -> Email:
    from urllib.parse import quote
    link = f"{settings.public_url}/reset-password?token={quote(token)}"
    if invite:
        subject = f"You've been invited to LedgerFlow AI{f' — {company_name}' if company_name else ''}"
        intro = f"Hi {name}, an administrator created a LedgerFlow AI account for you. Set your password to get started. This link expires in 72 hours."
        button = ("Set your password", link)
    else:
        subject = "Reset your LedgerFlow AI password"
        intro = f"Hi {name}, we received a request to reset your password. This link expires in 30 minutes and can be used once."
        button = ("Choose a new password", link)
    footer = "If you didn't expect this email, you can ignore it. Your password won't change."
    text = f"{intro}\n\n{button[0]}: {link}\n\n{footer}\n"
    return Email(to=to, to_name=name, subject=subject, text=text, html=_layout(subject, intro, button, footer=footer),
                 template="user_invite" if invite else "password_reset", company_id=company_id, user_id=user_id)


def approval_requested_email(to: str, name: str, *, invoice_id: str, invoice_number: str | None, supplier: str | None,
                             amount: str, level_name: str, submitted_by: str, company_id: str, user_id: str,
                             validation_status: str) -> Email:
    link = f"{settings.public_url}/app/invoices/{invoice_id}"
    num = invoice_number or "Untitled invoice"
    subject = f"Approval needed: {num} ({amount})"
    intro = f"Hi {name}, {submitted_by} submitted an invoice that needs your decision ({level_name})."
    rows = [("Invoice", num), ("Supplier", supplier or "—"), ("Amount", amount), ("Validation", validation_status)]
    text = f"{intro}\n\n" + "\n".join(f"{k}: {v}" for k, v in rows) + f"\n\nReview: {link}\n"
    return Email(to=to, to_name=name, subject=subject, text=text,
                 html=_layout(subject, intro, ("Review invoice", link), rows,
                              "You receive this because you are an approver in LedgerFlow AI."),
                 template="approval_requested", company_id=company_id, user_id=user_id)


def invoice_decided_email(to: str, name: str, *, invoice_id: str, invoice_number: str | None, amount: str,
                          decision: str, decided_by: str, reason: str | None, company_id: str, user_id: str) -> Email:
    link = f"{settings.public_url}/app/invoices/{invoice_id}"
    num = invoice_number or "Untitled invoice"
    subject = f"Invoice {num} {decision}"
    intro = f"Hi {name}, {decided_by} {decision} the invoice you submitted."
    rows = [("Invoice", num), ("Amount", amount), ("Decision", decision.title())]
    if reason:
        rows.append(("Reason", reason))
    text = f"{intro}\n\n" + "\n".join(f"{k}: {v}" for k, v in rows) + f"\n\nOpen: {link}\n"
    return Email(to=to, to_name=name, subject=subject, text=text,
                 html=_layout(subject, intro, ("Open invoice", link), rows), template=f"invoice_{decision}",
                 company_id=company_id, user_id=user_id)


def security_notice_email(to: str, name: str, *, event: str, company_id: str, user_id: str) -> Email:
    subject = f"Security alert: {event}"
    intro = (f"Hi {name}, this is a confirmation that the following happened on your LedgerFlow AI account: {event}. "
             "If this wasn't you, contact your administrator immediately.")
    return Email(to=to, to_name=name, subject=subject, text=intro, html=_layout(subject, intro, None),
                 template="security_notice", company_id=company_id, user_id=user_id)
