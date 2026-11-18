"""Test configuration: isolated SQLite DB + temp storage, no external services."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="ledgerflow-test-"))
os.environ.update({
    # Set TEST_DATABASE_URL=postgresql://... to run the suite against PostgreSQL.
    "APP_ENV": "test", "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", f"sqlite:///{(_TMP / 'test.db').as_posix()}"),
    "LOCAL_STORAGE_PATH": str(_TMP / "storage"), "JWT_SECRET": "test-jwt-secret-" + "x" * 32,
    "SECRET_KEY": "test-secret-key-" + "y" * 32, "AI_PROVIDER": "rules", "DEMO_MODE": "true", "STORAGE_PROVIDER": "local",
})

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.ratelimit import limiter  # noqa: E402
from app.demo.generate_documents import generate  # noqa: E402
from app.main import app  # noqa: E402

DOCS = _TMP / "docs"
PASSWORD = "Password123"


@pytest.fixture(scope="session", autouse=True)
def _schema():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    generate(DOCS)
    yield
    engine.dispose()


@pytest.fixture(autouse=True)
def _clean_db():
    limiter.enabled = False
    limiter._hits.clear()
    yield
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
            conn.exec_driver_sql(f"TRUNCATE {names} CASCADE")
        else:
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            for t in reversed(Base.metadata.sorted_tables):
                conn.exec_driver_sql(f'DELETE FROM "{t.name}"')
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


class Api:
    """Bearer-token client for one user."""

    def __init__(self, client: TestClient, token: str, me: dict):
        self.c, self.token, self.me = client, token, me
        self.h = {"Authorization": f"Bearer {token}"}

    def get(self, url, **kw):
        return self.c.get(f"/api/v1{url}", headers=self.h, **kw)

    def post(self, url, **kw):
        return self.c.post(f"/api/v1{url}", headers=self.h, **kw)

    def put(self, url, **kw):
        return self.c.put(f"/api/v1{url}", headers=self.h, **kw)

    def delete(self, url, **kw):
        return self.c.delete(f"/api/v1{url}", headers=self.h, **kw)

    def upload(self, path: Path, name: str | None = None, ctype: str = "application/octet-stream"):
        with path.open("rb") as fh:
            return self.post("/documents/upload", files={"file": (name or path.name, fh, ctype)})


def register(client: TestClient, company: str, email: str) -> Api:
    r = client.post("/api/v1/auth/register", json={"company_name": company, "full_name": "Owner", "email": email,
                                                   "password": PASSWORD, "gstin": None})
    assert r.status_code == 201, r.text
    client.cookies.clear()
    return Api(client, r.json()["access_token"], r.json())


def add_user(admin: Api, email: str, role: str) -> Api:
    r = admin.post("/users", json={"email": email, "full_name": role.title(), "role": role, "password": PASSWORD})
    assert r.status_code == 201, r.text
    r = admin.c.post("/api/v1/auth/login", json={"email": email, "password": PASSWORD})
    assert r.status_code == 200, r.text
    admin.c.cookies.clear()
    return Api(admin.c, r.json()["access_token"], r.json())


@pytest.fixture
def org(client):
    """A company with admin, accountant, approver and a supplier + PO matching scenario 01."""
    from app.demo.scenarios import BUYER, PURCHASE_ORDERS, SUPPLIERS
    admin = register(client, "Acme Test Co", "admin@acme-test.example")
    admin.put("/company", json={"gstin": BUYER["gstin"]})
    acc = add_user(admin, "acc@acme-test.example", "accountant")
    appr = add_user(admin, "appr@acme-test.example", "approver")
    sups = {}
    for code, s in SUPPLIERS.items():
        r = acc.post("/suppliers", json={"name": s["name"], "code": code, "gstin": s["gstin"], "payment_terms_days": s["terms"]})
        assert r.status_code == 201, r.text
        sups[code] = r.json()
    for p in PURCHASE_ORDERS:
        r = acc.post("/purchase-orders", json={
            "supplier_id": sups[p["supplier"]]["id"], "po_number": p["po_number"], "po_date": "2026-09-20",
            "items": [{"description": l.desc, "hsn_sac": l.hsn, "quantity": str(l.qty), "unit": l.unit,
                       "unit_price": str(l.price), "tax_rate": str(l.rate)} for l in p["lines"]]})
        assert r.status_code == 201, r.text
    return {"admin": admin, "acc": acc, "appr": appr, "suppliers": sups}


def doc(key: str) -> Path:
    return next(p for p in DOCS.iterdir() if p.stem == key)
