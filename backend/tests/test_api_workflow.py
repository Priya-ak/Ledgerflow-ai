import io

from openpyxl import load_workbook

from tests.conftest import add_user, doc


def _process(api, key):
    d = api.upload(doc(key))
    assert d.status_code == 201, d.text
    r = api.post("/invoices/extract", json={"document_id": d.json()["id"]})
    assert r.status_code == 201, r.text
    return r.json()


def test_end_to_end_upload_review_approve(org):
    acc, appr, admin = org["acc"], org["appr"], org["admin"]
    inv = _process(acc, "01_valid")
    assert inv["status"] == "extracted"
    assert inv["validation"]["status"] == "passed"
    assert inv["po_match_status"] == "matched"
    assert inv["supplier"]["code"] == "KST"
    assert inv["documents"][0]["status"] == "processed"
    assert inv["extracted_data"]["extraction_metadata"]["method"] == "rules"
    # Original document downloadable by the approver
    dl = appr.get(f"/documents/{inv['documents'][0]['id']}/download")
    assert dl.status_code == 200 and dl.content.startswith(b"%PDF")
    # Human correction is audited and re-validated
    r = acc.put(f"/invoices/{inv['id']}", json={"notes": "Checked with GRN-77", "payment_status": "unpaid"})
    assert r.status_code == 200 and r.json()["validation"]["status"] == "passed"
    r = acc.post(f"/invoices/{inv['id']}/submit", json={"note": "ok"})
    assert r.status_code == 200 and r.json()["status"] == "pending_approval"
    assert acc.put(f"/invoices/{inv['id']}", json={"notes": "x"}).status_code == 422  # locked while pending
    pending = appr.get("/approvals?actionable=true").json()
    assert pending["total"] == 1 and pending["items"][0]["can_decide"]
    r = appr.post(f"/invoices/{inv['id']}/approve", json={"comment": "Fine"})
    assert r.status_code == 200 and r.json()["status"] == "approved"
    actions = [a["action"] for a in admin.get(f"/audit-logs?entity_id={inv['id']}").json()["items"]]
    for a in ("invoice.extract", "invoice.correct", "invoice.submit", "invoice.approve"):
        assert a in actions
    ov = admin.get("/analytics/overview").json()
    assert ov["approved_count"] == 1 and ov["approved_amount"] == "19293.00"


def test_self_approval_blocked_and_reject_requires_reason(org):
    admin, acc = org["admin"], org["acc"]
    inv = _process(admin, "07_extra_items")
    admin.post(f"/invoices/{inv['id']}/submit", json={})
    r = admin.post(f"/invoices/{inv['id']}/approve", json={})
    assert r.status_code == 403  # admin submitted it himself
    appr = org["appr"]
    assert appr.post(f"/invoices/{inv['id']}/reject", json={"reason": ""}).status_code == 422
    r = appr.post(f"/invoices/{inv['id']}/reject", json={"reason": "Pallets were not ordered"})
    assert r.json()["status"] == "rejected"
    assert r.json()["approvals"][0]["steps"][0]["comment"] == "Pallets were not ordered"
    # Rejected invoice can be corrected and resubmitted by the accountant
    assert acc.put(f"/invoices/{inv['id']}", json={"notes": "Credit note requested"}).json()["status"] == "review_required"


def test_critical_errors_block_approval(org):
    acc, appr = org["acc"], org["appr"]
    inv = _process(acc, "02_wrong_gst")
    assert inv["validation"]["status"] == "failed" and inv["has_critical_errors"]
    line_tax = next(c for c in inv["validation"]["checks"] if c["code"] == "line_tax" and not c["passed"])
    assert line_tax["expected"] == "6408.00" and line_tax["actual"] == "4272.00"
    acc.post(f"/invoices/{inv['id']}/submit", json={})
    r = appr.post(f"/invoices/{inv['id']}/approve", json={"comment": "pls"})
    assert r.status_code == 422 and "critical" in r.json()["error"]["message"]
    r = appr.post(f"/invoices/{inv['id']}/approve", json={"comment": "override please", "override_critical": True})
    assert r.status_code == 403  # approvers cannot override


def test_correction_fixes_validation(org):
    acc = org["acc"]
    inv = _process(acc, "03_arith_mismatch")
    assert inv["validation"]["status"] == "failed"
    r = acc.put(f"/invoices/{inv['id']}", json={"grand_total": "96460.00"})
    assert r.json()["validation"]["status"] in ("passed", "warnings")
    assert not r.json()["has_critical_errors"]


def test_duplicate_detection_and_resolution(org):
    acc = org["acc"]
    first = _process(acc, "01_valid")
    dup = _process(acc, "05_duplicate")
    assert dup["duplicate_status"] == "duplicate"
    m = dup["duplicates"][0]
    assert m["matched_invoice_id"] == first["id"] and m["match_type"] == "exact"
    assert any("invoice number" in r for r in m["reasons"])
    assert acc.post(f"/invoices/{dup['id']}/submit", json={}).status_code == 422
    # Same file uploaded twice is detected by checksum
    again = _process(acc, "01_valid")
    assert any(d["match_type"] == "same_document" for d in again["duplicates"])
    r = acc.post(f"/invoices/{dup['id']}/duplicates/{m['id']}/resolve", json={"resolution": "not_duplicate", "note": "Supplier re-issued with new date"})
    assert r.json()["duplicate_status"] in ("resolved_not_duplicate", "duplicate")
    assert r.json()["duplicates"][0]["resolution"] == "not_duplicate" or any(d["resolution"] for d in r.json()["duplicates"])


def test_po_mismatch_and_multilevel_approval(org):
    acc, appr, admin = org["acc"], org["appr"], org["admin"]
    head = add_user(admin, "head@acme-test.example", "approver")
    admin.put("/company/approval-policy", json={"levels": [
        {"level": 1, "name": "Manager", "role": "approver", "min_amount": "0"},
        {"level": 2, "name": "Finance head", "role": "approver", "min_amount": "50000"}]})
    inv = _process(acc, "06_po_mismatch")
    assert inv["po_match_status"] == "mismatch"
    assert any("unit_price" in i for i in inv["po_match"]["issues"])
    acc.post(f"/invoices/{inv['id']}/submit", json={})
    r = appr.post(f"/invoices/{inv['id']}/approve", json={"comment": "L1 ok"})
    assert r.json()["status"] == "pending_approval" and r.json()["approvals"][0]["current_level"] == 2
    assert appr.post(f"/invoices/{inv['id']}/approve", json={}).status_code == 403  # same person twice
    r = head.post(f"/invoices/{inv['id']}/approve", json={"comment": "L2 ok"})
    assert r.json()["status"] == "approved" and len(r.json()["approvals"][0]["steps"]) == 2


def test_manual_po_rematch(org):
    acc = org["acc"]
    inv = _process(acc, "03_arith_mismatch")
    assert inv["po_match_status"] == "no_po_found"
    po = acc.get("/purchase-orders?q=PO-2026-0102").json()["items"][0]
    r = acc.post(f"/invoices/{inv['id']}/match-purchase-order", json={"purchase_order_id": po["id"]})
    assert r.json()["po_match_status"] == "mismatch"  # different supplier


def test_missing_fields_require_completion_before_submit(org):
    acc = org["acc"]
    inv = _process(acc, "04_missing_fields")
    assert inv["status"] == "review_required"
    assert acc.post(f"/invoices/{inv['id']}/submit", json={}).status_code == 422
    r = acc.put(f"/invoices/{inv['id']}", json={"invoice_number": "CE-24600", "invoice_date": "2026-10-20"})
    assert "invoice.invoice_number" not in r.json()["needs_review_fields"]
    assert acc.post(f"/invoices/{inv['id']}/submit", json={}).status_code == 200


def test_crud_and_listing(org):
    acc, admin = org["acc"], org["admin"]
    r = acc.post("/suppliers", json={"name": "New Vendor", "code": "NV1", "gstin": "33ABCDE1234F1Z9"})
    assert r.status_code == 422  # bad checksum rejected
    r = acc.post("/suppliers", json={"name": "New Vendor", "code": "NV1"})
    assert r.status_code == 201
    assert acc.post("/suppliers", json={"name": "Dup", "code": "NV1"}).status_code == 409
    sid = r.json()["id"]
    assert acc.put(f"/suppliers/{sid}", json={"name": "Renamed Vendor", "code": "NV1"}).json()["name"] == "Renamed Vendor"
    assert admin.delete(f"/suppliers/{sid}?hard=true").status_code == 200
    page = acc.get("/suppliers?q=steel&page_size=2").json()
    assert page["total"] == 1 and page["page_size"] == 2
    inv = acc.post("/invoices", json={"invoice_number": "M-1", "invoice_date": "2026-10-01", "supplier_id": org["suppliers"]["CEL"]["id"],
                                      "grand_total": "118.00", "taxable_amount": "100.00", "cgst": "9.00", "sgst": "9.00",
                                      "items": [{"description": "Bulb", "quantity": "1", "unit_price": "100.00", "taxable_value": "100.00",
                                                 "tax_rate": "18", "tax_amount": "18.00", "line_total": "118.00"}]})
    assert inv.status_code == 201
    lst = acc.get("/invoices?sort=-amount&q=M-1").json()
    assert lst["total"] == 1
    assert admin.delete(f"/invoices/{inv.json()['id']}").json()["status"] == "archived"
    assert acc.get("/invoices?q=M-1").json()["total"] == 0


def test_reports_and_excel_export(org):
    acc, appr = org["acc"], org["appr"]
    inv = _process(acc, "01_valid")
    acc.post(f"/invoices/{inv['id']}/submit", json={})
    appr.post(f"/invoices/{inv['id']}/approve", json={})
    _process(acc, "02_wrong_gst")
    js = acc.get("/reports/validation").json()
    assert js["total_rows"] >= 1 and "Severity" in js["columns"]
    r = appr.get("/reports/invoices/export?include=invoices,invoice-details,suppliers,validation,po-matching,approvals,monthly")
    assert r.status_code == 200 and "spreadsheetml" in r.headers["content-type"]
    wb = load_workbook(io.BytesIO(r.content))
    assert {"Invoice Register", "Validation Exceptions", "Approval History", "Monthly Summary"} <= set(wb.sheetnames)
    ws = wb["Invoice Register"]
    assert ws["A4"].value == "Invoice No" and ws.cell(row=ws.max_row, column=1).value == "Total"
    trends = acc.get("/analytics/invoices").json()
    assert sum(m["count"] for m in trends["monthly"]) >= 2
    assert acc.get("/analytics/suppliers").json()["suppliers"]


def test_system_status_reports_ai_and_ocr(org):
    s = org["acc"].get("/system/status").json()
    assert s["ai"]["provider"] == "rules" and s["ai"]["available"]
    assert s["database"] in ("sqlite", "postgresql")


def test_document_preview_and_utc_timestamps(org, client):
    acc, appr = org["acc"], org["appr"]
    inv = _process(acc, "01_valid")
    doc_id = inv["documents"][0]["id"]
    r = appr.get(f"/documents/{doc_id}/preview?page=1")
    assert r.status_code == 200 and r.content.startswith(b"\x89PNG")
    assert appr.get(f"/documents/{doc_id}/preview?page=9").status_code == 422
    img = _process(acc, "04_missing_fields")["documents"][0]["id"]
    assert acc.get(f"/documents/{img}/preview").content.startswith(b"\x89PNG")
    # Timestamps must carry a UTC offset so browsers render local time correctly.
    assert inv["created_at"].endswith(("+00:00", "Z"))
    logs = org["admin"].get(f"/audit-logs?entity_id={inv['id']}").json()["items"]
    assert all(l["created_at"].endswith(("+00:00", "Z")) for l in logs)
