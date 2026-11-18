import shutil

import pytest

from app.ml import providers
from app.schemas.extraction import ExtractedInvoice
from app.services.extraction import extract_fields, parse_date
from app.services.text_extraction import extract_text
from tests.conftest import doc

needs_tesseract = pytest.mark.skipif(shutil.which("tesseract") is None, reason="Tesseract not installed")


def test_pdf_text_extraction_and_fields():
    r = extract_text(doc("01_valid"), "pdf")
    assert r.method == "pdf_text"
    e = extract_fields(r.text)
    assert e.supplier.name == "Kaveri Steel Traders"
    assert e.invoice.invoice_number == "KST/26-27/0412"
    assert str(e.invoice.invoice_date) == "2026-10-04"
    assert e.invoice.purchase_order_number == "PO-2026-0101"
    assert e.supplier.gstin.startswith("33") and e.buyer.gstin.startswith("33")
    assert len(e.items) == 3 and str(e.items[2].discount) == "160.00"
    assert str(e.summary.grand_total) == "19293.00"
    assert not e.extraction_metadata.needs_review


@needs_tesseract
def test_ocr_image_missing_fields_are_null_and_flagged():
    r = extract_text(doc("04_missing_fields"), "png")
    assert r.method == "ocr" and r.ocr_confidence is not None
    e = extract_fields(r.text, ocr_confidence=r.ocr_confidence)
    assert e.invoice.invoice_number is None and e.invoice.invoice_date is None  # never invented
    assert "invoice.invoice_number" in e.extraction_metadata.review_fields
    assert e.extraction_metadata.needs_review
    assert len(e.items) == 1


@needs_tesseract
def test_ocr_noisy_scan():
    r = extract_text(doc("08_needs_review"), "jpeg")
    e = extract_fields(r.text)
    assert e.invoice.invoice_number == "DOS-INV-88390"
    assert e.summary.grand_total is not None


def test_unparseable_text_returns_nulls_not_guesses():
    e = extract_fields("hello world\nthis is not an invoice")
    assert e.invoice.invoice_number is None and e.summary.grand_total is None and e.items == []
    assert e.extraction_metadata.needs_review


def test_date_parsing_is_day_first():
    assert str(parse_date("04/10/2026")) == "2026-10-04"
    assert str(parse_date("4 Oct 2026")) == "2026-10-04"
    assert parse_date("31/02/2026") is None


def test_llm_suggestions_are_grounded_and_schema_validated():
    text = "ACME SUPPLIES\nInv Ref ZX-991 issued on 03/09/2026\nTotal 100"
    base = extract_fields(text)
    raw = '{"invoice_number": "ZX-991", "invoice_date": "03/09/2026", "supplier_name": "Hallucinated Corp", "grand_total": "999"}'
    merged = providers.merge_suggestions(base, providers.parse_llm_json(raw), text, "ollama")
    assert merged.invoice.invoice_number == "ZX-991"
    assert str(merged.invoice.invoice_date) == "2026-09-03"
    assert merged.supplier.name != "Hallucinated Corp"  # not in source text -> discarded
    assert merged.extraction_metadata.method == "rules+ollama"
    ExtractedInvoice.model_validate(merged.model_dump())


def test_malformed_llm_json_raises_ai_unavailable():
    with pytest.raises(providers.AiUnavailable):
        providers.parse_llm_json("sure! here you go: not json")
    with pytest.raises(providers.AiUnavailable):
        providers.parse_llm_json('{"invoice_number": ' + '"x' * 100 + '"}')


def test_ollama_unreachable_falls_back_to_rules(monkeypatch):
    monkeypatch.setattr(providers.settings, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(providers.settings, "OLLAMA_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(providers.settings, "AI_TIMEOUT_SECONDS", 1.0)
    base = extract_fields("Unknown layout text")
    out = providers.refine_with_fallback("Unknown layout text", base)
    assert out.extraction_metadata.method == "rules"
    assert any("unavailable" in w for w in out.extraction_metadata.warnings)


def test_gemini_requires_explicit_cloud_opt_in(monkeypatch):
    monkeypatch.setattr(providers.settings, "AI_PROVIDER", "gemini")
    monkeypatch.setattr(providers.settings, "GEMINI_API_KEY", "dummy")
    monkeypatch.setattr(providers.settings, "ALLOW_CLOUD_AI", False)
    out = providers.refine_with_fallback("text", extract_fields("text"))
    assert out.extraction_metadata.method == "rules"


def test_ollama_provider_against_mocked_api(monkeypatch):
    """Exercises the real OllamaProvider request/response handling with a mocked HTTP API.

    No model is executed here; this verifies payload limits, JSON parsing, schema
    validation and grounding - not model quality.
    """
    import httpx

    captured = {}

    def fake_post(url, json=None, timeout=None, **_):
        captured.update(url=url, body=json, timeout=timeout)
        return httpx.Response(200, json={"response": '{"invoice_number": "ZX-991", "buyer_name": "Not In Text Ltd"}'},
                              request=httpx.Request("POST", url))

    monkeypatch.setattr(providers.settings, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(providers.httpx, "post", fake_post)
    text = "ACME SUPPLIES\nRef ZX-991\n" + "filler line\n" * 500
    out = providers.refine_with_fallback(text, extract_fields(text))
    assert captured["url"].endswith("/api/generate")
    assert captured["body"]["options"]["num_ctx"] == providers.settings.OLLAMA_NUM_CTX
    assert captured["body"]["format"] == "json" and captured["body"]["options"]["temperature"] == 0
    assert len(captured["body"]["prompt"]) < providers.MAX_PROMPT_CHARS + 1000
    assert out.invoice.invoice_number == "ZX-991"
    assert out.buyer.name is None  # ungrounded suggestion rejected
    assert out.extraction_metadata.method == "rules+ollama"


def test_ollama_malformed_output_falls_back(monkeypatch):
    import httpx
    monkeypatch.setattr(providers.settings, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(providers.httpx, "post", lambda url, **_: httpx.Response(200, json={"response": "I think the invoice is..."}, request=httpx.Request("POST", url)))
    out = providers.refine_with_fallback("Ref ZX-991", extract_fields("Ref ZX-991"))
    assert out.extraction_metadata.method == "rules"


LAYOUT_A = """NILGIRI PACKAGING CO
Doc Ref: NPC-7781/26
Issued 12-Oct-2026   Pay by 11-Nov-2026
Customer order ref: PO-2026-0199
Seller GST Reg: 33AAFFK2001L1ZS
Ship & bill: Arunachala Engineering Works Pvt Ltd (DEMO)
Amount payable Rs 10,620.00"""

LAYOUT_B = """Bill from: Vellore Tools & Hardware
Reference number VTH-INV-00456 dated 3rd November 2026
Your PO number PO-2026-0201
GST No. 33AAJFC5004P1ZF
Total 4,720.00"""


def test_non_standard_layouts():
    a = extract_fields(LAYOUT_A)
    assert a.invoice.invoice_number == "NPC-7781/26"
    assert str(a.invoice.invoice_date) == "2026-10-12" and str(a.invoice.due_date) == "2026-11-11"
    assert a.invoice.purchase_order_number == "PO-2026-0199"
    assert a.supplier.name == "NILGIRI PACKAGING CO" and a.supplier.gstin == "33AAFFK2001L1ZS"
    assert a.buyer.name == "Arunachala Engineering Works Pvt Ltd (DEMO)"
    assert str(a.summary.grand_total) == "10620.00"
    b = extract_fields(LAYOUT_B)
    assert b.supplier.name == "Vellore Tools & Hardware"
    assert str(b.invoice.invoice_date) == "2026-11-03"
    assert b.invoice.purchase_order_number == "PO-2026-0201"
    # "Reference number" is deliberately not a rules label (ambiguous with PO refs) -> left for review / AI
    assert b.invoice.invoice_number is None and "invoice.invoice_number" in b.extraction_metadata.review_fields


def test_ordinal_dates():
    assert str(parse_date("3rd November 2026")) == "2026-11-03"
    assert str(parse_date("November 21st, 2026")) == "2026-11-21"


@pytest.mark.skipif(not __import__("os").environ.get("OLLAMA_TEST"), reason="set OLLAMA_TEST=1 with a running Ollama + model")
def test_real_ollama_model_fills_grounded_fields(monkeypatch):
    monkeypatch.setattr(providers.settings, "AI_PROVIDER", "ollama")
    monkeypatch.setattr(providers.settings, "AI_TIMEOUT_SECONDS", 180)
    out = providers.refine_with_fallback(LAYOUT_B, extract_fields(LAYOUT_B))
    # A 0.5B model is not deterministic; whatever it adds must be grounded in the text.
    if out.extraction_metadata.method == "rules+ollama":
        assert out.invoice.invoice_number in (None, "VTH-INV-00456")
    for f in out.extraction_metadata.ai_suggested_fields:
        assert f in ("invoice_number", "invoice_date", "due_date", "purchase_order_number", "supplier_name",
                     "supplier_gstin", "buyer_name", "buyer_gstin")
