import time

import pyotp

from app.core.ratelimit import limiter
from app.models import MfaRecoveryCode, User
from tests.conftest import PASSWORD, Api, register


def _enable(api: Api) -> tuple[str, list[str]]:
    setup = api.post("/auth/mfa/setup").json()
    assert setup["otpauth_uri"].startswith("otpauth://totp/") and setup["qr_svg"].lstrip().startswith("<?xml")
    secret = setup["secret"]
    r = api.post("/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200, r.text
    return secret, r.json()["recovery_codes"]


def _login(client, email, password=PASSWORD):
    client.cookies.clear()
    return client.post("/api/v1/auth/login", json={"email": email, "password": password})


def test_enrol_and_login_with_totp(client, db):
    api = register(client, "Co", "a@co.example")
    secret, codes = _enable(api)
    assert len(codes) == 10 and len(set(codes)) == 10
    # secret is encrypted at rest, never stored as plaintext
    u = db.query(User).filter_by(email="a@co.example").one()
    assert u.mfa_enabled and secret not in (u.mfa_secret_enc or "")
    assert db.query(MfaRecoveryCode).filter_by(user_id=u.id).count() == 10
    # enabling MFA revoked the old token
    assert api.get("/auth/me").status_code == 401

    r = _login(client, "a@co.example")
    assert r.status_code == 200 and r.json()["mfa_required"] is True
    assert "lf_session" not in r.cookies and "access_token" not in r.json()
    challenge = r.json()["mfa_token"]
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {challenge}"}).status_code == 401  # not a session

    assert client.post("/api/v1/auth/mfa/verify", json={"mfa_token": challenge, "code": "000000"}).status_code == 401
    # the code used during enrolment cannot be reused; the next 30 s code works
    used = pyotp.TOTP(secret).now()
    assert client.post("/api/v1/auth/mfa/verify", json={"mfa_token": challenge, "code": used}).status_code == 401
    code = pyotp.TOTP(secret).at(time.time() + 30)
    r = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": challenge, "code": code})
    assert r.status_code == 200 and r.json()["mfa"]["enabled"] and "lf_session" in r.cookies

    # the same code cannot be replayed
    challenge2 = _login(client, "a@co.example").json()["mfa_token"]
    assert client.post("/api/v1/auth/mfa/verify", json={"mfa_token": challenge2, "code": code}).status_code == 401


def test_recovery_code_works_once(client):
    api = register(client, "Co", "a@co.example")
    _, codes = _enable(api)
    ch = _login(client, "a@co.example").json()["mfa_token"]
    r = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": ch, "code": codes[0].upper()})
    assert r.status_code == 200 and r.json()["mfa"]["recovery_codes_remaining"] == 9
    ch = _login(client, "a@co.example").json()["mfa_token"]
    assert client.post("/api/v1/auth/mfa/verify", json={"mfa_token": ch, "code": codes[0]}).status_code == 401


def test_disable_requires_password_and_code(client):
    api = register(client, "Co", "a@co.example")
    secret, codes = _enable(api)
    ch = _login(client, "a@co.example").json()["mfa_token"]
    tok = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": ch, "code": pyotp.TOTP(secret).at(time.time() + 30)}).json()["access_token"]
    me = Api(client, tok, {})
    assert me.post("/auth/mfa/disable", json={"password": "wrong-password", "code": codes[1]}).status_code == 401
    assert me.post("/auth/mfa/disable", json={"password": PASSWORD, "code": codes[1]}).status_code == 200
    r = _login(client, "a@co.example")
    assert "mfa_required" not in r.json() or r.json()["mfa_required"] is False


def test_company_policy_forces_enrolment(client):
    admin = register(client, "Co", "boss@co.example")
    admin.post("/users", json={"email": "acc@co.example", "full_name": "Acc", "role": "accountant", "password": PASSWORD})
    r = admin.put("/company/settings", json={"currency": "INR", "amount_tolerance": "1.00", "po_price_tolerance_pct": "2.00",
                                             "po_qty_tolerance_pct": "0.00", "duplicate_window_days": 90, "require_mfa": True})
    assert r.status_code == 200
    r = _login(client, "acc@co.example")
    body = r.json()
    assert body["mfa"]["enrollment_required"] and body["permissions"] == []
    acc = Api(client, body["access_token"], body)
    blocked = acc.get("/invoices")
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "mfa_enrollment_required"
    secret, _ = _enable(acc)
    ch = _login(client, "acc@co.example").json()["mfa_token"]
    full = client.post("/api/v1/auth/mfa/verify", json={"mfa_token": ch, "code": pyotp.TOTP(secret).at(time.time() + 30)}).json()
    assert Api(client, full["access_token"], full).get("/invoices").status_code == 200
    # cannot switch it off while the policy requires it
    assert Api(client, full["access_token"], full).post("/auth/mfa/disable", json={"password": PASSWORD, "code": "123456"}).status_code == 422


def test_admin_can_reset_lost_device(client):
    admin = register(client, "Co", "boss@co.example")
    admin.post("/users", json={"email": "acc@co.example", "full_name": "Acc", "role": "accountant", "password": PASSWORD})
    tok = _login(client, "acc@co.example").json()["access_token"]
    acc = Api(client, tok, {})
    _enable(acc)
    uid = next(u["id"] for u in admin.get("/users").json()["items"] if u["email"] == "acc@co.example")
    r = admin.post(f"/users/{uid}/mfa/reset")
    assert r.status_code == 200 and r.json()["mfa_enabled"] is False
    assert _login(client, "acc@co.example").json().get("mfa_required") in (None, False)


def test_mfa_verify_is_rate_limited_per_account(client):
    api = register(client, "Co", "a@co.example")
    _enable(api)
    limiter.enabled = True
    codes = []
    for _ in range(7):
        ch = _login(client, "a@co.example").json().get("mfa_token")
        if not ch:
            codes.append(429)
            continue
        codes.append(client.post("/api/v1/auth/mfa/verify", json={"mfa_token": ch, "code": "111111"}).status_code)
    assert 429 in codes


def test_change_password(client):
    api = register(client, "Co", "a@co.example")
    assert api.post("/auth/change-password", json={"current_password": "nope", "new_password": "Another12345"}).status_code == 401
    r = api.post("/auth/change-password", json={"current_password": PASSWORD, "new_password": "Another12345"})
    assert r.status_code == 200
    assert api.get("/auth/me").status_code == 401  # old bearer token revoked
    assert _login(client, "a@co.example", "Another12345").status_code == 200
