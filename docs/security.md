# Security

## Controls implemented

| Area | Control |
|---|---|
| Passwords | bcrypt (cost 12); minimum 10 characters with letters and digits; 72-byte cap made explicit; change-password signs out other sessions and sends a security email |
| Sessions | HS256 JWT in an **httpOnly, SameSite=Lax** cookie (Secure outside development), 8 h expiry, issuer/type checks, `token_version` revocation on logout, password change/reset, role change, deactivation and MFA changes |
| **Two-factor authentication** | TOTP (RFC 6238) with QR enrolment; ±1 step drift; **replay protection** (a code is accepted once); 10 one-time recovery codes stored as HMAC hashes; secrets **encrypted at rest** (Fernet, `ENCRYPTION_KEY`); login issues a 5-minute challenge token that is useless as a session; per-account attempt limit; admin reset for lost devices; company policy **"require 2FA"** forces enrolment (restricted session that can only reach the enrolment endpoints) |
| Account enumeration | Identical responses for unknown emails (login and forgot-password); dummy hash on unknown users; reset emails are sent after the response so timing does not leak |
| Brute force | Per-IP limits (login 30/5 min, register 5/h, forgot 5/h, reset 10/h) and **per-account** limits (login 10/15 min, MFA 5/5 min) that hold even when attackers rotate IPs |
| Client IP behind proxies | `TRUSTED_PROXY_HOPS` takes the address added by our own proxies from `X-Forwarded-For`; client-supplied left-most values are never trusted |
| **Email** | Password reset (30 min, single use), user invitations (72 h), approval requests, approval/rejection notices, security alerts. Brevo HTTPS API, SMTP or console provider; delivery log **without bodies** (bodies contain one-time links); retries on transient failures |
| Authorization | Central role-to-permission map; every route declares its permission; segregation of duties (no self-approval, no approving two levels); last-admin protection |
| Tenant isolation | Company ID always comes from the authenticated user; `get_owned()` returns 404 for other tenants; covered by tests |
| Uploads | Streaming size limit, magic-byte sniffing, extension must match content, full parse by PyMuPDF/Pillow, decompression-bomb pixel limit, password-protected PDFs rejected, server-generated storage keys, display filename sanitised |
| **Malware** | **ClamAV** (clamd INSTREAM) scans raw bytes before any parser runs, failing closed (HTTP 503) if the scanner is unreachable. **PDF active-content policy**, always on: rejects JavaScript (including `#xx`-obfuscated names), launch actions, embedded files, rich media, XFA and import-data actions. Rejections are audited with engine and signature |
| File access | Private storage buckets; files served only through authorised endpoints with `nosniff` and `private, no-store` |
| **Backups** | Nightly encrypted, deduplicated snapshots to a private bucket; weekly automated restore drill; see [backups.md](backups.md) |
| Database exposure (Supabase) | Tables live in a dedicated `ledgerflow` schema that is **not exposed** to Supabase's Data API; the app connects as `ledgerflow_app`, a least-privilege role (no superuser, no role creation, 60 s statement timeout); `anon`/`authenticated` have no privileges |
| Secrets | Environment variables only; the frontend proxy keeps the backend URL server-side; the service-role key is used only by the backend; staging/production refuse to start without strong `JWT_SECRET`, `SECRET_KEY` and `ENCRYPTION_KEY` |
| AI | Off by default; cloud AI needs explicit `ALLOW_CLOUD_AI`; document text is framed as untrusted data; outputs are schema-validated and **grounded** (each value must appear verbatim in the document); models cannot change amounts or approve |
| Injection | SQLAlchemy ORM / bound parameters only; Pydantic validation on every request |
| Audit | Append-only `audit_logs` (ORM blocks update/delete); secrets scrubbed from metadata; request id and client IP recorded; malware rejections, MFA events and email-driven actions included |
| Errors | Generic 500 to clients; stack traces only in server logs with the request id |
| Headers | `nosniff`, `Referrer-Policy`, `X-Frame-Options: SAMEORIGIN`, `Permissions-Policy`; `X-Powered-By` removed |

## Known gaps (remaining)

1. **ClamAV is off on the free hosted demo.** clamd needs about 1 GB of RAM (measured), which does not fit Render's free instance or a 4 GB laptop alongside the app. The PDF active-content policy still runs everywhere. Enable `MALWARE_SCANNER=clamav` on any host with 2 GB+ RAM (docker-compose includes it).
2. **No SSO.** TOTP 2FA is built in; SAML/OIDC (Azure AD, Google Workspace) would be a client-specific integration.
3. **No CSRF token.** Mitigated by SameSite=Lax cookies, JSON-only APIs and same-origin proxying.
4. **The rate limiter is in-process** (single instance). Multiple instances need a shared store.
5. **Audit immutability is enforced in the application.** For production, add a DB role without UPDATE/DELETE on `audit_logs` or stream logs to WORM storage.
6. **No Content-Security-Policy** on the Next.js pages yet (the theme script is inline). Add a nonce-based CSP.
7. **Email deliverability:** a single verified Gmail sender works for demos, but corporate inboxes may flag it. Use a custom domain with SPF/DKIM/DMARC for client deployments.
8. **DPDP Act readiness** (retention schedules, consent records, deletion workflows) is not implemented.

Report security issues privately to the maintainer. Do not open public issues for vulnerabilities.
