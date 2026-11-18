"""GSTIN format and checksum validation (offline).

This is a FORMAT check only (structure + mod-36 check digit). It does not
confirm that a GSTIN is registered or active - that requires an authorised
GST Network integration, which LedgerFlow does not claim to provide.
"""
from __future__ import annotations

import re

GSTIN_RE = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")
_CHARS = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"

STATE_CODES = {
    "01": "Jammu and Kashmir", "02": "Himachal Pradesh", "03": "Punjab", "04": "Chandigarh",
    "05": "Uttarakhand", "06": "Haryana", "07": "Delhi", "08": "Rajasthan", "09": "Uttar Pradesh",
    "10": "Bihar", "11": "Sikkim", "12": "Arunachal Pradesh", "13": "Nagaland", "14": "Manipur",
    "15": "Mizoram", "16": "Tripura", "17": "Meghalaya", "18": "Assam", "19": "West Bengal",
    "20": "Jharkhand", "21": "Odisha", "22": "Chhattisgarh", "23": "Madhya Pradesh", "24": "Gujarat",
    "26": "Dadra and Nagar Haveli and Daman and Diu", "27": "Maharashtra", "29": "Karnataka",
    "30": "Goa", "31": "Lakshadweep", "32": "Kerala", "33": "Tamil Nadu", "34": "Puducherry",
    "35": "Andaman and Nicobar Islands", "36": "Telangana", "37": "Andhra Pradesh", "38": "Ladakh",
    "97": "Other Territory",
}


def normalize_gstin(value: str | None) -> str | None:
    if not value:
        return None
    v = re.sub(r"[^0-9A-Za-z]", "", value).upper()
    return v or None


def gstin_check_digit(first14: str) -> str:
    total = 0
    for i, ch in enumerate(first14):
        v = _CHARS.index(ch) * (2 if i % 2 else 1)
        total += v // 36 + v % 36
    return _CHARS[(36 - total % 36) % 36]


def validate_gstin(value: str | None) -> tuple[bool, str]:
    g = normalize_gstin(value)
    if not g:
        return False, "GSTIN is missing."
    if len(g) != 15 or not GSTIN_RE.match(g):
        return False, "GSTIN does not match the 15-character GST format."
    if g[:2] not in STATE_CODES:
        return False, f"GSTIN state code {g[:2]} is not a recognised state code."
    if gstin_check_digit(g[:14]) != g[14]:
        return False, "GSTIN check digit is invalid (possible typo or OCR error)."
    return True, "GSTIN format and check digit are valid (format check only)."


def make_gstin(state: str, pan: str, entity: str = "1") -> str:
    """Build a checksum-valid GSTIN. Used for synthetic demo data only."""
    first14 = f"{state}{pan}{entity}Z"
    return first14 + gstin_check_digit(first14)
