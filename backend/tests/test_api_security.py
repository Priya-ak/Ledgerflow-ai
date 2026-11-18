from tests.conftest import add_user, doc, register


def test_company_isolation(org, client):
    other = register(client, "Other Co", "boss@other.example")
    acc = org["acc"]
    d = acc.upload(doc("01_valid")).json()
    inv = acc.post("/invoices/extract", json={"document_id": d["id"]}).json()
    sup_id = org["suppliers"]["KST"]["id"]
    # Other tenant cannot see or touch anything (404, not 403, to avoid leaking existence)
    assert other.get(f"/invoices/{inv['id']}").status_code == 404
    assert other.put(f"/invoices/{inv['id']}", json={"notes": "x"}).status_code == 404
    assert other.get(f"/documents/{d['id']}/download").status_code == 404
    assert other.get(f"/suppliers/{sup_id}").status_code == 404
    assert other.post("/invoices/extract", json={"document_id": d["id"]}).status_code == 404
    assert other.get("/invoices").json()["total"] == 0
    assert other.get("/analytics/overview").json()["total_invoices"] == 0
    # Cannot attach another tenant's supplier to own invoice
    own = other.post("/invoices", json={"invoice_number": "X1", "supplier_id": sup_id})
    assert own.status_code == 404


def test_role_permissions(org):
    acc, appr, admin = org["acc"], org["appr"], org["admin"]
    assert appr.post("/suppliers", json={"name": "Zed", "code": "Z1"}).status_code == 403
    assert appr.upload(doc("01_valid")).status_code == 403
    assert acc.get("/audit-logs").status_code == 403
    assert acc.post("/users", json={"email": "x@acme-test.example", "full_name": "X", "role": "admin", "password": "Password123"}).status_code == 403
    assert acc.delete(f"/suppliers/{org['suppliers']['KST']['id']}").status_code == 403
    assert admin.get("/audit-logs").status_code == 200


def test_last_admin_cannot_be_demoted(org):
    admin = org["admin"]
    me = admin.me["user"]["id"]
    r = admin.put(f"/users/{me}", json={"role": "accountant"})
    assert r.status_code == 422


def test_role_change_revokes_sessions(org):
    admin, appr = org["admin"], org["appr"]
    admin.put(f"/users/{appr.me['user']['id']}", json={"role": "accountant"})
    assert appr.get("/auth/me").status_code == 401


def test_upload_rejects_spoofed_and_invalid_files(org, tmp_path):
    acc = org["acc"]
    fake = tmp_path / "invoice.pdf"
    fake.write_text("<script>alert(1)</script>")
    assert acc.upload(fake).status_code == 415
    png_named_pdf = tmp_path / "x.pdf"
    png_named_pdf.write_bytes(doc("04_missing_fields").read_bytes())
    assert acc.upload(png_named_pdf).status_code == 415
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"%PDF-1.4\n garbage")
    assert acc.upload(broken).status_code == 415
    empty = tmp_path / "empty.png"
    empty.write_bytes(b"")
    assert acc.upload(empty).status_code == 415
    big = tmp_path / "big.pdf"
    big.write_bytes(b"%PDF-" + b"0" * (11 * 1024 * 1024))
    assert acc.upload(big).status_code == 413


def test_upload_filename_traversal_is_neutralised(org):
    r = org["acc"].upload(doc("01_valid"), name="../../etc/passwd.pdf")
    assert r.status_code == 201
    assert "/" not in r.json()["original_filename"] and ".." not in r.json()["original_filename"].split("passwd")[0].strip(".")


def test_audit_log_is_immutable(org, db):
    import pytest
    from app.models import AuditLog
    from app.models.audit import AuditImmutableError
    entry = db.query(AuditLog).first()
    entry.action = "tampered"
    with pytest.raises(AuditImmutableError):
        db.flush()
    db.rollback()
    with pytest.raises(AuditImmutableError):
        db.delete(db.query(AuditLog).first())
        db.flush()
    db.rollback()


def test_error_envelope_has_request_id(client):
    r = client.get("/api/v1/invoices")
    body = r.json()["error"]
    assert body["code"] == "unauthorized" and body["request_id"] == r.headers["x-request-id"]
