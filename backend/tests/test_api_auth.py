from app.core.ratelimit import limiter
from tests.conftest import PASSWORD, register


def test_register_login_me_logout_revokes_token(client):
    api = register(client, "Co", "a@co.example")
    assert api.get("/auth/me").json()["user"]["role"] == "admin"
    r = client.post("/api/v1/auth/login", json={"email": "a@co.example", "password": PASSWORD})
    assert r.status_code == 200 and "lf_session" in r.cookies  # httpOnly session cookie
    token = r.json()["access_token"]
    h = {"Authorization": f"Bearer {token}"}
    assert client.post("/api/v1/auth/logout", headers=h).status_code == 200
    assert client.get("/api/v1/auth/me", headers=h).status_code == 401


def test_bad_credentials_and_weak_password(client):
    register(client, "Co", "a@co.example")
    assert client.post("/api/v1/auth/login", json={"email": "a@co.example", "password": "wrong"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": "nobody@co.example", "password": "x"}).status_code == 401
    r = client.post("/api/v1/auth/register", json={"company_name": "X", "full_name": "Y", "email": "b@co.example", "password": "short"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_duplicate_email_conflict(client):
    register(client, "Co", "a@co.example")
    r = client.post("/api/v1/auth/register", json={"company_name": "Co2", "full_name": "Yusuf", "email": "A@co.example", "password": PASSWORD})
    assert r.status_code == 409


def test_password_reset_flow(client):
    api = register(client, "Co", "a@co.example")
    r = client.post("/api/v1/auth/forgot-password", json={"email": "a@co.example"})
    token = r.json()["dev_reset_token"]
    assert token
    # unknown email -> identical generic response, no token
    r2 = client.post("/api/v1/auth/forgot-password", json={"email": "ghost@co.example"})
    assert r2.json()["message"] == r.json()["message"] and r2.json()["dev_reset_token"] is None
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "NewPassword99"}).status_code == 200
    assert api.get("/auth/me").status_code == 401  # old sessions revoked
    assert client.post("/api/v1/auth/reset-password", json={"token": token, "new_password": "NewPassword99"}).status_code == 422
    assert client.post("/api/v1/auth/login", json={"email": "a@co.example", "password": "NewPassword99"}).status_code == 200


def test_unauthenticated_and_tampered_tokens(client):
    assert client.get("/api/v1/invoices").status_code == 401
    assert client.get("/api/v1/invoices", headers={"Authorization": "Bearer abc.def.ghi"}).status_code == 401


def test_login_rate_limited(client):
    register(client, "Co", "a@co.example")
    limiter.enabled = True
    codes = [client.post("/api/v1/auth/login", json={"email": "a@co.example", "password": "bad"}).status_code for _ in range(12)]
    assert 429 in codes


def test_client_ip_from_trusted_proxy_chain(monkeypatch):
    from starlette.requests import Request

    from app.core import config, ratelimit

    def req(xff=None, peer="10.0.0.9"):
        headers = [(b"x-forwarded-for", xff.encode())] if xff else []
        return Request({"type": "http", "headers": headers, "client": (peer, 1234)})

    monkeypatch.setattr(config.settings, "TRUSTED_PROXY_HOPS", 0)
    assert ratelimit.client_ip(req("1.1.1.1")) == "10.0.0.9"  # proxies not trusted -> socket peer
    monkeypatch.setattr(config.settings, "TRUSTED_PROXY_HOPS", 2)
    # client spoofs a left-most value; we take the entry added by our first trusted proxy
    assert ratelimit.client_ip(req("6.6.6.6, 203.0.113.7, 76.76.21.1")) == "203.0.113.7"
    assert ratelimit.client_ip(req("203.0.113.7, 76.76.21.1")) == "203.0.113.7"


def test_per_account_login_limit_survives_ip_rotation(client):
    from app.core.ratelimit import limiter
    register(client, "Co", "a@co.example")
    limiter.enabled = True
    codes = [client.post("/api/v1/auth/login", json={"email": "a@co.example", "password": "bad"},
                         headers={"x-forwarded-for": f"198.51.100.{i}"}).status_code for i in range(12)]
    assert codes[:10] == [401] * 10 and 429 in codes[10:]
