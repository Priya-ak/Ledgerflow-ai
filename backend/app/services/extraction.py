"""Rule-based invoice field extraction (default, always available).

Uses labelled regular expressions over reconstructed text lines. Missing or
uncertain fields are returned as None and listed in review_fields - values
are never invented.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from app.schemas.extraction import (
    ExtractedInvoice, ExtractedItem, ExtractedParty, ExtractionMetadata,
)
from app.services.gst import GSTIN_RE, normalize_gstin, validate_gstin
from app.services.money import to_decimal

NUM = r"\(?-?\d[\d,]*(?:\.\d+)?\)?"
DATE = (r"(\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)?[\s\-][A-Za-z]{3,9}[\s\-,]+\d{4}"
        r"|[A-Za-z]{3,9}\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{4})")

RE_INVOICE_NO = re.compile(
    r"(?i)\b(?:(?:tax\s+)?(?:invoice|inv|bill)\s*(?:no\.?|number|num|#)|doc(?:ument)?\s*(?:ref|no\.?|number))"
    r"\s*[:\-#]?\s*([A-Z0-9][A-Z0-9\-/_.]{1,40})")
RE_INVOICE_DATE = re.compile(r"(?i)\b(?:invoice\s*date|inv\.?\s*date|date\s*of\s*invoice|bill\s*date|doc(?:ument)?\s*date|"
                             r"issued(?:\s*on)?|dated)\s*[:\-]?\s*" + DATE)
RE_DUE_DATE = re.compile(r"(?i)\b(?:due\s*date|payment\s*due|due\s*on|pay\s*by)\s*[:\-]?\s*" + DATE)
RE_PO_TOKEN = re.compile(r"\b(P\.?O[-/][A-Z0-9][A-Z0-9\-/_]{2,40})", re.I)
RE_PO = re.compile(
    r"(?i)\b(?:purchase\s*order|p\.?\s?o\.?)(?!\s*box)\s*(?:no\.?|number|ref\.?|#)?\s*[:\-#]?\s*([A-Z0-9][A-Z0-9\-/_]{2,40})")
RE_GSTIN_LOOSE = re.compile(r"\b[0-9OISB]{2}[A-Z0-9]{5}[0-9OISB]{4}[A-Z0-9][0-9A-Z]{1}[Z2][0-9A-Z]\b")
# A party label must be followed by ':'/'-' or end the line, so "Customer order ref:" is not a buyer.
RE_BUYER_LABEL = re.compile(r"(?i)^\s*(bill(?:ed)?\s*to|buyer|customer|ship(?:ped)?\s*to|sold\s*to|recipient|ship\s*&\s*bill)"
                            r"\s*(?:[:\-]\s*(.*)|$)")
RE_SELLER_LABEL = re.compile(r"(?i)^\s*(from|bill(?:ed)?\s*from|seller|supplier|vendor|sold\s*by)\s*(?:[:\-]\s*(.*)|$)")
RE_STOP = re.compile(r"(?i)\b(description|hsn|gstin|gst\s*no|invoice|date|phone|tel|email|e-mail|pan|state|place\s+of\s+supply|po\b|p\.o\.)")

SUMMARY_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("subtotal", re.compile(r"(?i)^\s*(sub\s*-?\s*total|total\s+before\s+(?:tax|discount)|gross\s+amount)\b")),
    ("discount", re.compile(r"(?i)^\s*(less\s*:?\s*)?discount\b")),
    ("taxable_total", re.compile(r"(?i)^\s*(total\s+)?taxable\s*(amount|value|total)?\b")),
    ("cgst", re.compile(r"(?i)^\s*(add\s*:?\s*)?cgst\b")),
    ("sgst", re.compile(r"(?i)^\s*(add\s*:?\s*)?(sgst|utgst)\b")),
    ("igst", re.compile(r"(?i)^\s*(add\s*:?\s*)?igst\b")),
    ("total_tax", re.compile(r"(?i)^\s*total\s+(tax|gst)\b")),
    ("other_charges", re.compile(r"(?i)^\s*(other\s+charges|freight|shipping|packing(\s+charges)?|round\s*(ing)?\s*off)\b")),
    ("grand_total", re.compile(r"(?i)^\s*(grand\s+total|total\s+amount(\s+payable)?|amount\s+payable|invoice\s+total|net\s+payable|total\s+payable|balance\s+due)\b")),
]

ITEM_RE = re.compile(
    rf"^(?:(?P<sn>\d{{1,3}})[.)]?\s+)?(?P<desc>[A-Za-z][^\n]*?)\s+(?P<hsn>\d{{4,8}})\s+(?P<qty>{NUM})"
    rf"(?:\s+(?P<unit>[A-Za-z]{{1,8}}\.?))?\s+(?P<nums>(?:{NUM}%?\s*){{3,6}})$"
)
ITEM_NO_HSN_RE = re.compile(
    rf"^(?:(?P<sn>\d{{1,3}})[.)]?\s+)?(?P<desc>[A-Za-z][^\n]*?[A-Za-z)])\s+(?P<qty>{NUM})"
    rf"\s+(?P<unit>[A-Za-z]{{1,8}}\.?)\s+(?P<nums>(?:{NUM}%?\s*){{3,6}})$"
)

_DATE_FORMATS = ["%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y", "%d/%m/%y", "%d-%m-%y", "%d.%m.%y", "%Y-%m-%d",
                 "%d %b %Y", "%d %B %Y", "%d-%b-%Y", "%d-%B-%Y", "%b %d %Y", "%B %d %Y", "%d %b, %Y"]


def parse_date(raw: str | None) -> date | None:
    """Parse a date. Numeric dates use the Indian day-first convention."""
    if not raw:
        return None
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", raw, flags=re.I)
    s = re.sub(r"\s+", " ", s.replace(",", " ")).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt.replace(",", "")).date()
        except ValueError:
            continue
    return None


def _fix_gstin_ocr(token: str) -> str:
    """Correct common OCR confusions using GSTIN positional structure."""
    t = list(token.upper())
    to_digit = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2"}
    to_alpha = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"}
    for i in (0, 1, 7, 8, 9, 10):
        t[i] = to_digit.get(t[i], t[i])
    for i in (2, 3, 4, 5, 6, 11):
        t[i] = to_alpha.get(t[i], t[i])
    t[13] = "Z" if t[13] == "2" else t[13]
    return "".join(t)


RE_GSTIN_LABEL = re.compile(r"(?i)\bGST(?:IN|\s*no\.?|\s*number)\s*[:\-]?\s*([A-Z0-9][A-Z0-9 ]{14,22})")


def _find_gstins(line: str, unreadable: list[str] | None = None) -> list[str]:
    found = []
    for m in RE_GSTIN_LOOSE.finditer(line.upper()):
        tok = m.group(0)
        cand = tok if GSTIN_RE.match(tok) else _fix_gstin_ocr(tok)
        if GSTIN_RE.match(cand):
            found.append(cand)
    if not found and (lm := RE_GSTIN_LABEL.search(line)):
        # OCR often splits a GSTIN with a space: join, then try positional fixes.
        tok = lm.group(1).replace(" ", "").upper()[:15]
        if len(tok) == 15:
            cand = tok if GSTIN_RE.match(tok) else _fix_gstin_ocr(tok)
            if GSTIN_RE.match(cand):
                found.append(cand)
            elif unreadable is not None:
                unreadable.append(lm.group(1).strip())
    return found


def _last_number(line: str) -> Decimal | None:
    nums = re.findall(NUM, line)
    # skip trailing percentages like "CGST @ 9%" -> use the amount, not the rate
    for n in reversed(nums):
        idx = line.rfind(n)
        if idx + len(n) < len(line) and line[idx + len(n)] == "%":
            continue
        return to_decimal(n)
    return None


def _clean(s: str | None) -> str | None:
    if s is None:
        return None
    s = re.sub(r"\s+", " ", s).strip(" :-,")
    return s or None


def _parse_item(line: str) -> ExtractedItem | None:
    m = ITEM_RE.match(line) or ITEM_NO_HSN_RE.match(line)
    if not m:
        return None
    raw_nums = re.findall(rf"{NUM}%?", m.group("nums"))
    rate = None
    nums: list[Decimal] = []
    for tok in raw_nums:
        if tok.endswith("%"):
            rate = to_decimal(tok[:-1])
        else:
            d = to_decimal(tok)
            if d is None:
                return None
            nums.append(d)
    item = ExtractedItem(description=_clean(m.group("desc")), hsn_sac=m.groupdict().get("hsn"),
                         quantity=to_decimal(m.group("qty")), unit=_clean(m.group("unit")))
    # Positional mapping by column count. Unknown layouts leave fields None.
    if rate is None:
        if len(nums) == 6:
            item.unit_price, item.discount, item.taxable_value, item.tax_rate, item.tax_amount, item.line_total = nums
        elif len(nums) == 5:
            item.unit_price, item.taxable_value, item.tax_rate, item.tax_amount, item.line_total = nums
        elif len(nums) == 3:
            item.unit_price, item.taxable_value, item.line_total = nums
        else:
            return None
    else:
        item.tax_rate = rate
        if len(nums) == 5:
            item.unit_price, item.discount, item.taxable_value, item.tax_amount, item.line_total = nums
        elif len(nums) == 4:
            item.unit_price, item.taxable_value, item.tax_amount, item.line_total = nums
        elif len(nums) == 3:
            item.unit_price, item.tax_amount, item.line_total = nums
        else:
            return None
    if item.tax_rate is not None and item.tax_rate > 100:
        return None  # not a plausible tax-rate column -> likely misparsed row
    return item


def _left_of_label(ln: str) -> str | None:
    """Text before the first label on a line (right-hand columns often share the line)."""
    m = RE_STOP.search(ln)
    if m is None:
        return ln
    return ln[:m.start()].strip() or None


def _party_block(lines: list[str], start: int, first: str | None) -> tuple[str | None, str | None]:
    """Name = first meaningful line, address = following lines until a stop label."""
    name = _clean(_left_of_label(first)) if first else None
    addr: list[str] = []
    for ln in lines[start + 1: start + 6]:
        if not ln.strip() or RE_BUYER_LABEL.match(ln) or _parse_item(ln):
            break
        part = _left_of_label(ln)
        if part is None:
            break
        if name is None:
            name = _clean(part)
        else:
            addr.append(part)
    return name, (_clean(", ".join(addr)) if addr else None)


def extract_fields(text: str, *, text_method: str | None = None, ocr_confidence: float | None = None,
                   extra_warnings: list[str] | None = None) -> ExtractedInvoice:
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    result = ExtractedInvoice()
    warnings = list(extra_warnings or [])
    joined = "\n".join(lines)

    # Header fields ---------------------------------------------------------
    if m := RE_INVOICE_NO.search(joined):
        cand = m.group(1).strip(".-/")
        if not re.fullmatch(r"(?i)date|dated", cand):
            result.invoice.invoice_number = cand
    if m := RE_INVOICE_DATE.search(joined):
        result.invoice.invoice_date = parse_date(m.group(1))
        if result.invoice.invoice_date is None:
            warnings.append(f"Could not parse invoice date '{m.group(1)}'.")
    if m := RE_DUE_DATE.search(joined):
        result.invoice.due_date = parse_date(m.group(1))
    if m := RE_PO_TOKEN.search(joined):  # a complete "PO-2026-0101" style token wins
        result.invoice.purchase_order_number = m.group(1).strip(".-/").upper().replace("P.O", "PO")
    elif m := RE_PO.search(joined):
        result.invoice.purchase_order_number = m.group(1).strip(".-/")

    # Parties --------------------------------------------------------------
    buyer_idx = next((i for i, ln in enumerate(lines) if RE_BUYER_LABEL.match(ln)), None)
    seller_idx = next((i for i, ln in enumerate(lines) if RE_SELLER_LABEL.match(ln)), None)
    unreadable: list[str] = []
    gstin_hits = [(i, g) for i, ln in enumerate(lines) for g in _find_gstins(ln, unreadable)]
    for raw in unreadable:
        warnings.append(f"A GSTIN label was found but its value is unreadable ('{raw}'). Enter it manually.")

    if seller_idx is not None and (buyer_idx is None or seller_idx < buyer_idx):
        name, addr = _party_block(lines, seller_idx, RE_SELLER_LABEL.match(lines[seller_idx]).group(2))
    else:
        # Convention: the issuing supplier's name heads the document.
        title = re.compile(r"(?i)\b(tax\s+invoice|invoice|original(\s+for\s+recipient)?|duplicate|triplicate|copy)\b")
        limit = buyer_idx if buyer_idx is not None else 8
        top = next((i for i, ln in enumerate(lines[:min(limit, 8)])
                    if re.search(r"[A-Za-z]{3}", title.sub("", ln)) and not RE_STOP.search(title.sub("", ln))), None)
        name, addr = (_party_block(lines, top, title.sub("", lines[top])) if top is not None else (None, None))
    result.supplier = ExtractedParty(name=name, address=addr)

    if buyer_idx is not None:
        bname, baddr = _party_block(lines, buyer_idx, RE_BUYER_LABEL.match(lines[buyer_idx]).group(2))
        result.buyer = ExtractedParty(name=bname, address=baddr)
        sup_g = [g for i, g in gstin_hits if i < buyer_idx]
        buy_g = [g for i, g in gstin_hits if i >= buyer_idx]
        result.supplier.gstin = sup_g[0] if sup_g else None
        result.buyer.gstin = buy_g[0] if buy_g else None
    elif gstin_hits:
        result.supplier.gstin = gstin_hits[0][1]
        if len(gstin_hits) > 1:
            result.buyer.gstin = gstin_hits[1][1]
        warnings.append("No 'Bill To' section found; GSTINs assigned by order of appearance.")

    for party in (result.supplier, result.buyer):
        if party.gstin and not validate_gstin(party.gstin)[0]:
            warnings.append(f"GSTIN {party.gstin} failed the check-digit test; it may be misread.")

    # Line items -------------------------------------------------------------
    for ln in lines:
        if any(p.match(ln) for _, p in SUMMARY_PATTERNS):
            continue
        if item := _parse_item(ln):
            result.items.append(item)

    # Summary ----------------------------------------------------------------
    for ln in lines:
        for key, pat in SUMMARY_PATTERNS:
            if pat.match(ln):
                val = _last_number(ln)
                if val is None:
                    continue
                if key == "other_charges":
                    cur = result.summary.other_charges or Decimal("0")
                    result.summary.other_charges = cur + val
                elif getattr(result.summary, key) is None:
                    setattr(result.summary, key, val)
                break

    if result.summary.grand_total is None:
        # Fallback: a bare "Total" line (not "Total Tax"/"Total Taxable")
        for ln in reversed(lines):
            if re.match(r"(?i)^\s*total\b(?!\s+(tax|gst|taxable|qty|quantity))", ln):
                result.summary.grand_total = _last_number(ln)
                warnings.append("Grand total taken from a generic 'Total' line.")
                break

    if re.search(r"₹|\bINR\b|\bRs\.?\b", joined) or result.supplier.gstin or result.buyer.gstin:
        result.invoice.currency = "INR"

    # Review flags --------------------------------------------------------------
    important = {
        "supplier.name": result.supplier.name, "supplier.gstin": result.supplier.gstin,
        "invoice.invoice_number": result.invoice.invoice_number, "invoice.invoice_date": result.invoice.invoice_date,
        "buyer.name": result.buyer.name, "buyer.gstin": result.buyer.gstin,
        "summary.taxable_total": result.summary.taxable_total, "summary.grand_total": result.summary.grand_total,
    }
    review = [k for k, v in important.items() if v is None]
    if not result.items:
        review.append("items")
        warnings.append("No line items could be parsed; enter them manually.")
    low_conf = ocr_confidence is not None and ocr_confidence < 70
    result.extraction_metadata = ExtractionMetadata(
        method="rules", text_method=text_method, ocr_confidence=ocr_confidence,
        needs_review=bool(review or warnings or low_conf), review_fields=review, warnings=warnings,
    )
    return result
